"""The monthly digest node: the month's synthesis from the cluster logs."""

import logging
from datetime import date, timedelta
from typing import Any

from hipeac_agents.agents.vision_watch import settings as watch_settings
from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.cluster.tallies import (
    entries_through,
    persistence,
    reach,
    sort_ranked,
    strongest,
    tally_text,
)
from hipeac_agents.agents.vision_watch.schemas import ClusterEntry
from hipeac_agents.services.factory import Services
from hipeac_agents.services.mail import markdown_to_html
from hipeac_agents.services.urls import display_domain
from hipeac_agents.storage import WorkspaceError

from .models import MonthlyBottomLine, TrendProse
from .prompts import MONTHLY_BOTTOM_LINE, MONTHLY_TREND


logger = logging.getLogger(__name__)


def month_weeks(month: str) -> set[str]:
    """Week labels whose closing Friday falls in a calendar month.

    :param month: A calendar month as ``"YYYY-MM"``.
    :returns: Week labels such as ``{"2026-W27", ..., "2026-W31"}``.
    """
    year, mon = (int(part) for part in month.split("-"))
    day = date(year, mon, 1)
    weeks: set[str] = set()

    while day.month == mon:
        day += timedelta(days=(4 - day.weekday()) % 7 or 7)
        iso = day.isocalendar()
        weeks.add(f"{iso.year}-W{iso.week:02d}")
        day = day + timedelta(days=1)

    return weeks


def compose_monthly_markdown(
    month: str,
    themes: list[str],
    cluster_data: dict[str, dict[str, Any]],
    prose: dict[str, TrendProse],
    bottom_line: str,
) -> str:
    """Assemble the monthly digest markdown, two tiers deep.

    Sections per compose-digest.md's monthly template: Bottom line; Candidate
    trends (threshold-crossing clusters, full anatomy + the news so far);
    Also accumulating (one line each — name, tally, Europe tag, recommendation);
    Theme health; Quiet/closed. Below-threshold clusters get a line, not a
    section: only threshold-crossed evidence earns the full anatomy.

    :param month: The calendar month as ``"YYYY-MM"``.
    :param themes: The watched theme ids, in digest order.
    :param cluster_data: Cluster id to ``{theme, cluster, entries, month_entries, weeks_active}``.
    :param prose: Cluster id to the synthesis the LLM wrote, when generated.
    :param bottom_line: The Bottom line text.
    :returns: The full monthly digest markdown.
    """
    lines: list[str] = [
        f"# HiPEAC Vision Watch — {month}",
        "",
        "## Bottom line",
        "",
        bottom_line,
        "",
    ]

    ranked = sort_ranked(
        [(data["cluster"], data["entries"]) for data in cluster_data.values()],
        _catalog(),
    )
    candidates = [cluster.id for cluster, _ in ranked if _crossed(cluster_data[cluster.id])]
    progressing = [
        cluster.id
        for cluster, _ in ranked
        if not _crossed(cluster_data[cluster.id]) and len(cluster_data[cluster.id]["month_entries"]) >= 1
    ]

    lines.extend(["## Candidate trends", ""])

    if candidates:
        for cid in candidates:
            lines.extend(_trend_section(cid, cluster_data[cid], prose, month))
    else:
        lines.append("(No cluster crossed the candidate-trend threshold this month.)")

    lines.append("")
    lines.extend(
        [
            "## Also accumulating",
            "",
            "(Clusters below the candidate-trend threshold that received entries this month.",
            "One line each; full anatomy comes when they cross.)",
            "",
        ]
    )

    if progressing:
        for cid in progressing:
            item = prose.get(cid)
            europe = _europe_tag(item.europe) if item else ""
            recommendation = _recommendation(item.recommendation) if item else "keep watching"
            lines.append(
                f"- **{cid}** ({cluster_data[cid]['theme']}) — {tally_text(cluster_data[cid]['entries'])} · "
                f"Europe: {europe} · {recommendation}"
            )
    else:
        lines.append("(No clusters accumulated entries this month.)")

    lines.append("")
    lines.extend(["## Theme health", ""])

    for theme in themes:
        theme_entries = [d for d in cluster_data.values() if d["theme"] == theme]
        month_new = sum(len(d["month_entries"]) for d in theme_entries)

        if not theme_entries or month_new == 0:
            lines.append(f"- **{theme}:** quiet — no new entries this month.")
        else:
            growing = theme_clusters_of(theme, cluster_data)
            lines.append(
                f"- **{theme}:** growing — {month_new} new "
                f"entr{'y' if month_new == 1 else 'ies'} across {len(growing)} "
                f"cluster{'s' if len(growing) != 1 else ''} this month."
            )

    lines.append("")
    lines.extend(["## Quiet / closed", ""])

    quiet = [cid for cid, data in cluster_data.items() if _dormant(data, month_weeks(month))]

    if quiet:
        for cid in sorted(quiet):
            lines.append(f"- **{cid}** ({tally_text(cluster_data[cid]['entries'])}) — no entries this month.")
    else:
        lines.append("(Every cluster received entries this month.)")

    lines.append("")
    return "\n".join(lines)


def theme_clusters_of(theme: str, cluster_data: dict[str, dict[str, Any]]) -> list[str]:
    """Cluster ids belonging to one theme.

    :param theme: The theme id.
    :param cluster_data: Cluster id to cluster data.
    :returns: The cluster ids in that theme.
    """
    return [cid for cid, data in cluster_data.items() if data["theme"] == theme]


def _crossed(data: dict[str, Any]) -> bool:
    """Check the documented candidate-trend threshold for a cluster.

    :param data: Cluster data with ``entries``.
    :returns: ``True`` when the cluster crosses the threshold.
    """
    from hipeac_agents.agents.vision_watch.nodes.cluster.tallies import is_candidate_trend

    return is_candidate_trend(data["entries"])


def _dormant(data: dict[str, Any], weeks: set[str]) -> bool:
    """Check a cluster received no entries this month.

    :param data: Cluster data with ``month_entries``.
    :param weeks: Unused; the month's entries decide.
    :returns: ``True`` when the cluster has no entries in the month.
    """
    return len(data["month_entries"]) == 0


def _catalog():
    """Read the source catalog, for the ranking's independence discount."""
    return workspace.read_source_catalog()


def _europe_tag(europe: str) -> str:
    """Extract the GAP/OPPORTUNITY/DEPENDENCY tag from a Europe sentence.

    :param europe: The Europe sentence from the synthesis.
    :returns: The tag, or ``"—"`` when none is present.
    """
    for tag in ("GAP", "OPPORTUNITY", "DEPENDENCY"):
        if tag in europe.upper():
            return tag
    return "—"


def _recommendation(recommendation: str) -> str:
    """Normalise a recommendation to its short form.

    :param recommendation: The recommendation sentence from the synthesis.
    :returns: ``"adopt"``, ``"keep watching"``, or ``"let go"``.
    """
    lowered = recommendation.lower()
    if "adopt" in lowered:
        return "adopt"
    if "let go" in lowered:
        return "let go"
    return "keep watching"


def _trend_section(cid: str, data: dict[str, Any], prose: dict[str, TrendProse], month: str) -> list[str]:
    """Render one cluster's monthly section: prose plus the month's news.

    :param cid: The cluster id.
    :param data: The cluster's data.
    :param prose: Cluster id to the synthesis the LLM wrote, when generated.
    :param month: The calendar month as ``"YYYY-MM"``.
    :returns: Markdown lines for the section.
    """
    item = prose.get(cid)

    if item is None:
        raise WorkspaceError(f"missing monthly prose for cluster '{cid}' — every rendered cluster needs a synthesis")

    lines = [
        f"### {item.trend_name} — ({_tally_all(data)})",
        "",
        item.evidence_summary,
        "",
        f"- Why it matters: {item.why_it_matters}",
        f"- Confidence: {item.confidence}",
        f"- Likelihood: {item.likelihood}",
        f"- Europe: {item.europe}",
        f"- Recommendation: {item.recommendation}",
        "",
    ]
    lines.append("News so far:")

    for entry in data["month_entries"]:
        lines.append(f"- _{entry.note or entry.title}_ — [{display_domain(entry.url)}]({entry.url})")

    lines.append("")
    return lines


def _tally_all(data: dict[str, Any]) -> str:
    """Render the cluster's tally through this month.

    :param data: The cluster's data.
    :returns: The tally string.
    """
    entries = data["entries"]
    weeks = persistence(entries)

    return (
        f"{len(entries)} finding{'s' if len(entries) != 1 else ''} · "
        f"{reach(entries)} source class{'es' if reach(entries) != 1 else ''} · "
        f"{weeks} week{'s' if weeks != 1 else ''}"
    )


async def monthly_node(
    state: Any,
    *,
    services: Services,
    llm: Any,
) -> dict[str, Any]:
    """Compose the month's synthesis from the cluster logs and write it.

    Reads every cluster log; clusters active in the month get a synthesis
    (trend named, evidence so far, recommendation); theme health and the
    dormant list close the digest. Writes ``digests/monthly/digest-YYYY-MM.md``.

    :param state: The graph state; carries ``month``.
    :param services: The wired services (mail for the send step).
    :param llm: The chat model used for the synthesis calls.
    :returns: State updates: digest markdown, sent flag.
    """
    month = state.month

    # Preflight: the monthly digest is write-once, so synthesising a month
    # that already has one would pay for every prose call and then raise on
    # the write. A digest composed once is also a digest sent once.
    if recorded := workspace.read_monthly_digest(month):
        logger.info("month %s already has a digest; skipping synthesis and send", month)
        return {"digest_markdown": recorded, "digest_sent": False}

    themes = [theme.theme for theme in workspace.read_themes()]
    weeks = month_weeks(month)

    cluster_data: dict[str, dict[str, Any]] = {}

    for theme in themes:
        log = workspace.read_cluster_log(theme)

        if log is None:
            continue

        boundary_week = max(weeks) if weeks else None

        for cluster in log.clusters:
            scoped = entries_through(cluster.entries, boundary_week) if boundary_week else cluster.entries

            if not scoped:
                continue

            month_entries = [entry for entry in scoped if entry.week in weeks]

            cluster_data[cluster.id] = {
                "theme": theme,
                "cluster": cluster,
                "entries": scoped,
                "month_entries": month_entries,
                "best": strongest(scoped),
            }

    active = {cid: data for cid, data in cluster_data.items() if data["month_entries"]}
    prose: dict[str, TrendProse] = {}

    if active:
        ranked = sort_ranked([(data["cluster"], data["entries"]) for data in active.values()], _catalog())

        for cluster, _entries in ranked:
            data = active[cluster.id]
            month_news = "\n".join(
                f"- {entry.week} [{entry.source_id}] {entry.note or entry.title} ({entry.url}, tier {entry.tier})"
                for entry in data["month_entries"]
            )
            prose[cluster.id] = await _trend_prose(
                llm,
                f"Cluster: {cluster.id} (theme: {data['theme']})\n"
                f"Tally through {month}: {_tally_all(data)}\n"
                f"Entries this month ({month}):\n{month_news}\n"
                f"Independence check: low-independence share of entries through {month} is "
                f"{_independence_share(data['entries']):.0%}.",
            )

    bottom_line = await _bottom_line(
        llm,
        "\n".join(
            f"{cid} ({data['theme']}): {_tally_all(data)}, {len(data['month_entries'])} entries this month; "
            f"strongest entry: {data['best'].note} ({data['best'].url})"
            for cid, data in sorted(active.items(), key=lambda item: -len(item[1]["entries"]))[:6]
        ),
    )
    markdown = compose_monthly_markdown(month, themes, cluster_data, prose, bottom_line.text.strip())
    workspace.write_monthly_digest(month, markdown)

    sent = False
    recipient = watch_settings.HIPEAC_VISION_BOARD_EMAIL
    inbox = watch_settings.AGENTMAIL_INBOX_VISION_WATCH

    if services.mail is not None and inbox and recipient and state.send:
        await services.mail.send(
            inbox,
            recipient,
            subject=bottom_line.text[:100],
            text=markdown,
            html=markdown_to_html(markdown),
            reply_to=watch_settings.HIPEAC_VISION_REPLY_TO,
        )
        sent = True

    return {"digest_markdown": markdown, "digest_sent": sent}


async def _trend_prose(llm: Any, context: str) -> TrendProse:
    """Write one cluster's monthly synthesis.

    LLM judgement call (monthly trend synthesis) — see ``prompts.MONTHLY_TREND``.
    """
    runner = llm.with_structured_output(TrendProse)
    return await runner.ainvoke(MONTHLY_TREND + "\n\nCluster material:\n" + context)


async def _bottom_line(llm: Any, context: str) -> MonthlyBottomLine:
    """Write the Bottom line section.

    LLM judgement call (monthly bottom line) — see ``prompts.MONTHLY_BOTTOM_LINE``.
    """
    runner = llm.with_structured_output(MonthlyBottomLine)
    return await runner.ainvoke(MONTHLY_BOTTOM_LINE + "\n\nMonth material:\n" + context)


def _independence_share(entries: list[ClusterEntry]) -> float:
    """Share of a cluster's entries from low-independence sources.

    :param entries: The cluster's entries through this month.
    :returns: Share (0.0-1.0) of low-independence entries.
    """
    catalog = _catalog()
    independence = {source.id: source.independence for source in catalog.sources}

    if not entries:
        return 0.0

    low = sum(1 for entry in entries if independence.get(entry.source_id) == "low")
    return low / len(entries)


def _catalog():
    """Read the source catalog, for ranking and independence."""
    return workspace.read_source_catalog()
