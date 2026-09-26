"""The digest node's orchestration: prose calls, markdown assembly, write, send."""

import logging
from typing import Any

from hipeac_agents.agents.vision_watch import settings as watch_settings
from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.cluster.tallies import (
    entries_through,
    is_candidate_trend,
    sort_lead_candidates,
    sort_ranked,
    strongest,
    tally_text,
    threshold_progress,
    trend_status,
)
from hipeac_agents.agents.vision_watch.schemas import Cluster, RejectedItem, SourceCatalog, ThemeDef
from hipeac_agents.agents.vision_watch.state import VisionWatchState
from hipeac_agents.services.factory import Services
from hipeac_agents.services.mail import markdown_to_html
from hipeac_agents.services.urls import display_domain

from .models import DigestProse, InBrief, SignalGroup, SignalGroups
from .prompts import DIGEST_IN_BRIEF, DIGEST_ITEM, DIGEST_SIGNALS


logger = logging.getLogger(__name__)

# Per-theme entry cap in "Across the themes": a week flooded by a high-volume
# feed must not print every entry, only its strongest.
_MAX_THEME_ENTRIES = 12


async def _item_prose(llm: Any, context: str) -> DigestProse:
    """Write one digest item's prose.

    LLM judgement call (digest item anatomy) — see ``prompts.DIGEST_ITEM``.
    """
    runner = llm.with_structured_output(DigestProse)
    return await runner.ainvoke(DIGEST_ITEM + "\n\nItem material:\n" + context)


async def _in_brief(llm: Any, context: str) -> InBrief:
    """Write the ~100-word In brief section.

    LLM judgement call (digest prose) — see ``prompts.DIGEST_IN_BRIEF``.
    """
    runner = llm.with_structured_output(InBrief)
    return await runner.ainvoke(DIGEST_IN_BRIEF + "\n\nDigest material:\n" + context)


async def _signal_groups(llm: Any, rejects: list[RejectedItem], themes: list[ThemeDef]) -> SignalGroups:
    """Group off-theme rejects that collectively point to a shared dynamic.

    LLM judgement call (signal triage) — see ``prompts.DIGEST_SIGNALS``.
    """
    theme_text = "\n".join(f"- {t.theme}: {t.definition}" for t in themes)
    rejects_text = "\n".join(f"- {r.url} — {r.claimed_title}: {r.summary}" for r in rejects)
    runner = llm.with_structured_output(SignalGroups)
    return await runner.ainvoke(
        DIGEST_SIGNALS + f"\n\nWatched themes:\n{theme_text}\n\nThis week's off-theme rejects:\n{rejects_text}"
    )


def _collect_off_theme_rejects(week: str) -> list[RejectedItem]:
    """Read this week's off-theme rejects, the signal-triage call's input.

    :param week: The week label.
    :returns: The week's off-theme rejects, or an empty list if none.
    """
    rejected_file = workspace.read_rejected_file(week)

    if rejected_file is None:
        return []

    return [item for item in rejected_file.rejected if item.reason == "off_theme"]


def _collect_clusters(week: str, themes: list[str]) -> dict[str, dict[str, Any]]:
    """Collect every cluster of the watched themes, scoped through this week.

    Entries recorded after ``week`` are excluded, so a digest re-composed
    later for the same week reports the same tally.

    :param week: The week label.
    :param themes: The watched theme ids, in digest order.
    :returns: Cluster id to ``{theme, cluster, entries, this_week}``.
    """
    cluster_data: dict[str, dict[str, Any]] = {}

    for theme in themes:
        log = workspace.read_cluster_log(theme)

        if log is None:
            continue

        for cluster in log.clusters:
            scoped = entries_through(cluster.entries, week)

            if not scoped:
                continue

            cluster_data[cluster.id] = {
                "theme": theme,
                "cluster": cluster,
                "entries": scoped,
                "this_week": [entry for entry in scoped if entry.week == week],
            }

    return cluster_data


def _lead_cluster(
    touched: dict[str, dict[str, Any]], week: str, catalog: SourceCatalog
) -> tuple[str, dict[str, Any]] | None:
    """Pick the week's lead cluster — the "One big thing" — via ``sort_lead_candidates``.

    :param touched: Cluster id to cluster data, clusters with entries this week only.
    :param week: The week label.
    :param catalog: The parsed source catalog, for the independence discount.
    :returns: ``(cluster id, cluster data)`` of the lead, or ``None`` when nothing was touched.
    """
    if not touched:
        return None

    candidates: list[tuple[Cluster, list[Any], list[Any]]] = [
        (data["cluster"], data["entries"], data["this_week"]) for data in touched.values()
    ]
    top_cluster, _, _ = sort_lead_candidates(candidates, week, catalog)[0]
    return top_cluster.id, touched[top_cluster.id]


def compose_digest_markdown(
    week: str,
    themes: list[str],
    cluster_data: dict[str, dict[str, Any]],
    prose: dict[str, DigestProse],
    in_brief: str,
    signal_groups: list[SignalGroup] | None = None,
) -> str:
    """Assemble the digest markdown from this week's cluster entries.

    Sections: In brief; One big thing (the week's lead cluster, full item
    anatomy); Across the themes (every cluster touched this week, one line
    each); Also worth watching (off-theme rejects grouped into a shared
    signal, when any coherent group was found); Trending this week (standing
    evidence weight, ranked).

    :param week: The week label.
    :param themes: The watched theme ids, in digest order.
    :param cluster_data: Cluster id to ``{theme, cluster, entries, this_week}``.
    :param prose: Cluster id to the lead cluster's prose, when generated.
    :param in_brief: The In brief text.
    :param signal_groups: This week's signal-triage groups, if any.
    :returns: The full digest markdown.
    """
    touched = {cid: data for cid, data in cluster_data.items() if data["this_week"]}
    signal_groups = signal_groups or []

    lines: list[str] = [
        f"# HiPEAC Vision Watch — Week {week}",
        "",
        "## In brief",
        "",
        in_brief,
        "",
    ]

    lead = _lead_cluster(touched, week, _catalog())

    if lead is not None:
        top_id, top_data = lead
        item = prose.get(top_id)
        best = strongest(top_data["this_week"])
        lines.extend(
            [
                "## One big thing",
                "",
                f"**_{item.lead if item else best.note}_** — [{display_domain(best.url)}]({best.url})",
                "",
            ]
        )
        if item:
            lines.extend(
                [
                    f"- Why it matters: {item.why_it_matters}",
                    f"- Europe: {item.europe}",
                    f"- Maturity and confidence: {item.maturity} ({tally_text(top_data['entries'])})",
                ]
            )
        lines.append("")

    lines.extend(["## Across the themes", ""])

    for theme in themes:
        theme_clusters = [(cid, data) for cid, data in touched.items() if data["theme"] == theme]

        if not theme_clusters:
            lines.extend([f"### {theme}", "", "Quiet week — no entries this window.", ""])
            continue

        lines.extend([f"### {theme}", ""])

        by_finding: dict[str, dict[str, Any]] = {}
        for cid, data in theme_clusters:
            for entry in data["this_week"]:
                found = by_finding.setdefault(entry.finding_id, {"entry": entry, "cluster_ids": []})
                found["cluster_ids"].append(cid)

        ranked = sorted(
            by_finding.values(),
            key=lambda found: (found["entry"].tier, -found["entry"].date.toordinal()),
        )

        for found in ranked[:_MAX_THEME_ENTRIES]:
            entry = found["entry"]
            text = entry.note or entry.title
            cluster_ids = ", ".join(found["cluster_ids"])
            lines.append(f"- _{text}_ — [{display_domain(entry.url)}]({entry.url}) — in {cluster_ids}")

        if len(ranked) > _MAX_THEME_ENTRIES:
            lines.append(
                f"- (+{len(ranked) - _MAX_THEME_ENTRIES} more entries this week — see the theme's cluster log.)"
            )

        lines.append("")

    # Board tips: a tip is an editor-flagged lead, recorded verbatim every
    # time — even when the grouping call placed it in no cluster, where the
    # theme sections would lose it.
    findings_file = workspace.read_findings_file(week)
    tips = [f for f in (findings_file.findings if findings_file else []) if f.source_id == "board-tip"]
    if tips:
        lines.extend(["## Board tips this week", ""])
        for tip in tips:
            lines.append(f"- _{tip.summary}_ — [{display_domain(tip.url)}]({tip.url})")
        lines.append("")

    if signal_groups:
        lines.extend(["## Also worth watching", ""])
        for group in signal_groups:
            links = ", ".join(f"[{display_domain(url)}]({url})" for url in group.urls)
            lines.append(f"- _{group.blurb}_ — {links}")
        lines.append("")

    # Trending this week: the main clusters with movement, ranked by weight.
    trending = sort_ranked(
        [(data["cluster"], data["entries"]) for data in touched.values()],
        _catalog(),
    )[:10]

    lines.extend(
        [
            "## Trending this week",
            "",
            "(Evidence status: a converged story has enough independent, sustained",
            "evidence for the board to consider naming it in the Vision.)",
            "",
        ]
    )

    if trending:
        for cluster, _entries in trending:
            data = touched[cluster.id]
            status = (
                "converged — consider naming it in the Vision"
                if is_candidate_trend(data["entries"])
                else "still gathering evidence"
            )
            lines.append(
                f"- **{cluster.id}** ({data['theme']}): {len(data['this_week'])} new this week. "
                f"Evidence so far: {tally_text(data['entries'])}. Status: {status}."
            )
    else:
        lines.append("(No clusters with movement this window.)")

    lines.append("")
    return "\n".join(lines)


async def digest_node(
    state: VisionWatchState,
    *,
    services: Services,
    llm: Any,
) -> dict[str, Any]:
    """Compose the weekly pulse from the cluster logs, write it, send it.

    The digest is built from the week's actual cluster entries, scoped
    through the week — so re-runs of the same week compose identically.

    :param state: The graph state; carries the week.
    :param services: The wired services (mail for the send step).
    :param llm: The chat model used for the lead item's prose call.
    :returns: State updates: digest markdown, sent flag.
    """
    week = state.week

    # Preflight: the digest is write-once, so composing a week that already
    # has one would pay for every prose call and then raise on the write. A
    # recorded digest is still sendable once — compose, review, then --send.
    if recorded := workspace.read_weekly_digest(week):
        logger.info("week %s already has a digest; skipping composition", week)
        themes = [theme.theme for theme in workspace.read_themes()]
        touched = {cid: data for cid, data in _collect_clusters(week, themes).items() if data["this_week"]}
        lead = _lead_cluster(touched, week, _catalog())
        sent = await _send(services, state, week, recorded, lead[1]["cluster"].name if lead else None)
        return {"digest_markdown": recorded, "digest_sent": sent}

    theme_defs = workspace.read_themes()
    themes = [theme.theme for theme in theme_defs]
    cluster_data = _collect_clusters(week, themes)
    catalog = _catalog()

    touched = {cid: data for cid, data in cluster_data.items() if data["this_week"]}
    lead = _lead_cluster(touched, week, catalog)

    prose: dict[str, DigestProse] = {}

    if lead is not None:
        lead_id, lead_data = lead
        best = strongest(lead_data["this_week"])
        prose[lead_id] = await _item_prose(
            llm,
            f"Cluster: {lead_id} (theme: {lead_data['theme']})\n"
            f"Strongest entry: {best.note} ([source]({best.url}), {best.date})\n"
            f"Tally: {tally_text(lead_data['entries'])}\n"
            f"Status: {trend_status(lead_data['entries'])}\n"
            f"Threshold progress: {threshold_progress(lead_data['entries'])}",
        )

    ranked_ids = [
        cluster.id for cluster, _ in sort_ranked([(d["cluster"], d["entries"]) for d in touched.values()], catalog)
    ]

    if lead is not None and lead_id in ranked_ids:
        ranked_ids.remove(lead_id)
        ranked_ids.insert(0, lead_id)

    in_brief = await _in_brief(
        llm,
        "\n".join(
            f"{cid} ({touched[cid]['theme']}): "
            f"{strongest(touched[cid]['this_week']).note} ({strongest(touched[cid]['this_week']).url})"
            for cid in ranked_ids[:5]
        ),
    )
    off_theme_rejects = _collect_off_theme_rejects(week)
    signal_groups = (await _signal_groups(llm, off_theme_rejects, theme_defs)).groups if off_theme_rejects else []

    markdown = compose_digest_markdown(week, themes, cluster_data, prose, in_brief.text.strip(), signal_groups)
    workspace.write_weekly_digest(week, markdown)

    sent = await _send(services, state, week, markdown, lead[1]["cluster"].name if lead is not None else None)
    return {"digest_markdown": markdown, "digest_sent": sent}


async def _send(services: Services, state: VisionWatchState, week: str, markdown: str, lead_name: str | None) -> bool:
    """Email a week's digest to the board, at most once and only with ``--send``.

    :param services: The wired services (mail).
    :param state: The graph state; carries the ``send`` opt-in.
    :param week: The week label.
    :param markdown: The digest markdown.
    :param lead_name: The lead cluster's name, for the subject; ``None`` on a quiet week.
    :returns: ``True`` when the digest was sent by this run.
    """
    recipient = watch_settings.HIPEAC_VISION_BOARD_EMAIL
    inbox = watch_settings.AGENTMAIL_INBOX_VISION_WATCH

    if not (state.send and services.mail is not None and inbox and recipient):
        return False
    if workspace.weekly_digest_sent(week):
        logger.info("week %s digest was already sent; not sending again", week)
        return False

    message_id = await services.mail.send(
        inbox,
        recipient,
        subject=f"HiPEAC Vision Watch — Week {week}: {lead_name or 'Quiet week'}",
        text=markdown,
        html=markdown_to_html(markdown),
        reply_to=watch_settings.HIPEAC_VISION_REPLY_TO,
    )
    workspace.mark_weekly_digest_sent(week, message_id)
    return True


def _catalog():
    """Read the source catalog, for the ranking's independence discount."""
    return workspace.read_source_catalog()
