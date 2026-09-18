"""The cluster node's orchestration: grouping call, log appends, tallies."""

from datetime import date
from typing import Any

from hipeac_agents.agents.vision_watch import schemas, workspace
from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterLog, Finding, SourceClass
from hipeac_agents.agents.vision_watch.state import ClusterReport, VisionWatchState
from hipeac_agents.agents.vision_watch.workspace import ClusterExistsError, EntryAlreadyRecordedError
from hipeac_agents.services.factory import Services

from .models import GroupingPlan
from .prompts import GROUPING_BAR
from .tallies import is_candidate_trend, sort_ranked, trend_status


async def _group_findings(
    llm: Any,
    themes: list[schemas.ThemeDef],
    cluster_index: dict[str, tuple[str, schemas.Cluster]],
    findings: list[Finding],
) -> GroupingPlan:
    """Ask the grouping-bar judgement call — one global call for the week.

    The call sees every cluster across every theme and every finding, so one
    development gets one cluster identity instead of per-theme duplicates.

    LLM judgement call (grouping bar) — see ``prompts.GROUPING_BAR``.

    :param llm: The chat model.
    :param themes: The watched themes, for definitions.
    :param cluster_index: Cluster id to ``(theme, cluster)`` across all themes.
    :param findings: The week's findings.
    :returns: The grouping plan.
    """
    theme_text = "\n".join(f"- {t.theme}: {t.definition}" for t in themes)
    existing = (
        "\n".join(
            f"- {cid} [theme: {theme}] ({len(cluster.entries)} entries, opened {cluster.opened})"
            + (" | recent: " + " | ".join(entry.note for entry in cluster.entries[-3:]) if cluster.entries else "")
            for cid, (theme, cluster) in sorted(cluster_index.items())
        )
        or "(no clusters yet)"
    )
    findings_text = "\n".join(
        f"- {f.id} [themes: {', '.join(f.theme_ids) or 'none'}]: {f.title} — {f.summary}" for f in findings
    )
    runner = llm.with_structured_output(GroupingPlan)

    return await runner.ainvoke(
        GROUPING_BAR
        + f"\n\nWatched themes:\n{theme_text}"
        + f"\n\nExisting clusters (all themes):\n{existing}\n\nThis week's findings:\n{findings_text}"
    )


def _entry_from_finding(week: str, finding: Finding, catalog: schemas.SourceCatalog) -> schemas.ClusterEntry:
    """Build a cluster entry from a finding.

    The entry's descriptive text is the finding's summary — a one-sentence
    account of what happened, written once at harvest time. The grouping
    call's note was dropped: it restated the summary without adding
    information, and cost one judgement per assignment.

    :param week: The current week label.
    :param finding: The finding to record.
    :param catalog: The parsed source catalog, for the source's class.
    :returns: The cluster entry.
    """
    classes: dict[str, SourceClass] = {s.id: s.source_class for s in catalog.sources}

    return schemas.ClusterEntry(
        week=week,
        finding_id=finding.id,
        source_id=finding.source_id,
        source_class=classes.get(finding.source_id, "community"),
        tier=finding.tier,
        region=finding.region,
        date=finding.date,
        title=finding.title,
        note=finding.summary,
        url=finding.url,
    )


async def cluster_node(
    state: VisionWatchState,
    *,
    services: Services,
    llm: Any,
) -> dict[str, Any]:
    """Group the week's findings into clusters and update the append-only logs.

    One global grouping call sees all clusters (all themes) and all findings,
    so a development gets one cluster identity regardless of theme. New
    clusters are created in the theme the call assigns; entries append to the
    owning theme's log.

    Findings come from the week's findings file, not the graph state — a
    digest run has no harvest node in front of it.

    :param state: The graph state; carries the week.
    :param services: Unused — the cluster node has no service boundary.
    :param llm: The chat model used for the grouping-bar judgement call.
    :returns: State updates: cluster reports, derived notes for the digest.
    """
    week = state.week
    catalog = workspace.read_source_catalog()
    themes = workspace.read_themes()
    # The digest run has no harvest in its graph; the week's findings file is
    # the input either way.
    findings_file = workspace.read_findings_file(week)
    findings = list(findings_file.findings) if findings_file else []

    # Index every existing cluster across all themes.
    cluster_index: dict[str, tuple[str, schemas.Cluster]] = {}
    logs: dict[str, ClusterLog] = {}
    for theme in themes:
        log = workspace.read_cluster_log(theme.theme) or ClusterLog(
            theme=theme.theme, created=date.today(), clusters=[]
        )
        logs[theme.theme] = log
        for cluster in log.clusters:
            cluster_index[cluster.id] = (theme.theme, cluster)

    # Record-once: reuse the week's grouping decision on rerun.
    plan = workspace.read_grouping_plan(week)
    if plan is None:
        plan = await _group_findings(llm, themes, cluster_index, findings)
        workspace.write_grouping_plan(week, plan.model_dump_json(indent=2))

    assigned_ids = {a.finding_id for a in plan.assignments}
    extended_by_theme: dict[str, int] = {theme.theme: 0 for theme in themes}
    opened_by_theme: dict[str, int] = {theme.theme: 0 for theme in themes}
    reports: list[ClusterReport] = []
    notes: list[str] = []

    for assignment in plan.assignments:
        finding = next((f for f in findings if f.id == assignment.finding_id), None)

        if finding is None:
            continue

        entry = _entry_from_finding(week, finding, catalog)

        # Resolve the owning theme: existing cluster's theme, or the new
        # cluster's declared theme (falling back to the finding's first).
        if assignment.extends_cluster_id and assignment.extends_cluster_id in cluster_index:
            theme_name = cluster_index[assignment.extends_cluster_id][0]
        elif assignment.new_cluster:
            theme_name = assignment.new_cluster.theme
            if theme_name not in logs:
                theme_name = finding.theme_ids[0] if finding.theme_ids else themes[0].theme
        else:
            continue

        log = logs[theme_name]

        if assignment.extends_cluster_id and assignment.extends_cluster_id in cluster_index:
            try:
                workspace.append_cluster_entry(theme_name, assignment.extends_cluster_id, entry)
                extended_by_theme[theme_name] += 1
            except EntryAlreadyRecordedError:
                pass  # Re-run of the same week: the finding is already recorded.
        elif assignment.new_cluster:
            cluster = Cluster(
                id=assignment.new_cluster.id,
                name=assignment.new_cluster.name,
                opened=week,
                entries=[entry],
            )

            try:
                workspace.append_cluster(cluster, theme_name, log.created)
                opened_by_theme[theme_name] += 1
                cluster_index[cluster.id] = (theme_name, cluster)
            except ClusterExistsError:
                # Re-run: the cluster already exists; append the entry instead.
                try:
                    workspace.append_cluster_entry(theme_name, assignment.new_cluster.id, entry)
                    extended_by_theme[theme_name] += 1
                except EntryAlreadyRecordedError:
                    pass  # Re-run of the same week: the finding is already recorded.

    # Per-theme reports from the refreshed logs.
    for theme in themes:
        log = workspace.read_cluster_log(theme.theme) or logs[theme.theme]
        pairs = [(c, c.entries) for c in log.clusters]
        candidate_trends = [c.id for c, e in sort_ranked([(c, e) for c, e in pairs if is_candidate_trend(e)], catalog)]
        theme_unmatched = [f.id for f in findings if theme.theme in f.theme_ids and f.id not in assigned_ids]
        reports.append(
            ClusterReport(
                theme=theme.theme,
                clusters_extended=extended_by_theme[theme.theme],
                clusters_opened=opened_by_theme[theme.theme],
                findings_unmatched=theme_unmatched,
                candidate_trends=candidate_trends,
                notes=[f"{c.id} is {trend_status(e)}" for c, e in pairs],
            )
        )

    unmatched = [f.id for f in findings if f.id not in assigned_ids]

    if unmatched:
        notes.append(f"findings that joined no cluster: {', '.join(unmatched)}")

    return {"cluster_reports": reports, "notes": notes}
