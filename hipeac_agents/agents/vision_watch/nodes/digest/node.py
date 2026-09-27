"""The digest node's orchestration: story selection, one prose call, assembly, write, send."""

import logging
import re
from typing import Any

from hipeac_agents.agents.vision_watch import settings as watch_settings
from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.cluster.tallies import (
    entries_through,
    is_candidate_trend,
    sort_lead_candidates,
    tally_text,
    trend_status,
)
from hipeac_agents.agents.vision_watch.schemas import ClusterEntry, Finding, SourceCatalog, ThemeDef
from hipeac_agents.agents.vision_watch.state import VisionWatchState
from hipeac_agents.services.factory import Services
from hipeac_agents.services.mail import markdown_to_html
from hipeac_agents.services.urls import display_domain

from .models import StoryDigest
from .prompts import DIGEST_STORIES


logger = logging.getLogger(__name__)

# The digest's budget: the board reads at most this many stories per theme.
# The model sees a few more candidates than it may write, so it can leave the
# weak ones out; everything else is kept in the week's signals log.
MAX_STORIES_PER_THEME = 2
STORY_CANDIDATES_PER_THEME = 4
FINDINGS_PER_STORY = 4

QUIET_WEEK = StoryDigest(headline="Quiet week", this_week="No new signals reached the watch this week.")

_CITATION = re.compile(r"\[([^\]]+)\]\((F\d+)\)")
_BARE_CITATION = re.compile(r"\s*[\[(](F\d+)[\])]")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _collect_clusters(week: str, themes: list[str]) -> dict[str, dict[str, Any]]:
    """Collect every cluster of the themes, scoped through this week.

    Entries recorded after ``week`` are excluded, so a digest re-composed
    later for the same week sees the same tallies.

    :param week: The week label.
    :param themes: The theme ids, in digest order.
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


def _ranked(entries: list[ClusterEntry]) -> list[ClusterEntry]:
    return sorted(entries, key=lambda entry: (-(entry.significance or 3), -entry.date.toordinal()))


def story_candidates(
    week: str, themes: list[ThemeDef], cluster_data: dict[str, dict[str, Any]], catalog: SourceCatalog
) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """Pick each theme's candidate stories: its clusters that moved this week, strongest first.

    Ranked like the old lead story — forward significance, then novelty —
    and cut to ``STORY_CANDIDATES_PER_THEME``.

    :param week: The week label.
    :param themes: The themes, in digest order.
    :param cluster_data: Cluster id to ``{theme, cluster, entries, this_week}``.
    :param catalog: The source catalog, for the independence discount.
    :returns: Theme id to ``(cluster id, cluster data)`` pairs.
    """
    touched = {cid: data for cid, data in cluster_data.items() if data["this_week"]}
    candidates: dict[str, list[tuple[str, dict[str, Any]]]] = {}

    for theme in themes:
        mine = [(d["cluster"], d["entries"], d["this_week"]) for d in touched.values() if d["theme"] == theme.theme]
        ranked = sort_lead_candidates(mine, week, catalog)[:STORY_CANDIDATES_PER_THEME]
        candidates[theme.theme] = [(cluster.id, touched[cluster.id]) for cluster, _, _ in ranked]

    return candidates


def story_material(
    themes: list[ThemeDef],
    candidates: dict[str, list[tuple[str, dict[str, Any]]]],
    forward_notes: dict[str, str],
) -> tuple[str, dict[str, str]]:
    """Render the prose call's input, numbering every finding it may cite.

    :param themes: The themes, in digest order.
    :param candidates: Theme id to its candidate stories.
    :param forward_notes: Finding id to its forward note, when it has one.
    :returns: ``(material, refs)`` — refs maps each ``F<n>`` to the finding's URL.
    """
    refs: dict[str, str] = {}
    blocks: list[str] = []

    for theme in themes:
        lines = [f'THEME "{theme.theme}" ({theme.heading}) — {theme.description.strip()}']
        if theme.questions:
            lines.append(f"Open questions: {' '.join(theme.questions)}")

        stories = candidates.get(theme.theme, [])
        if not stories:
            lines.append("(no stories this week)")

        for _cluster_id, data in stories:
            lines.append(
                f'Story "{data["cluster"].name}" — {trend_status(data["entries"])}; '
                f"{tally_text(data['entries'])}; {len(data['this_week'])} new this week"
            )
            for entry in _ranked(data["this_week"])[:FINDINGS_PER_STORY]:
                ref = f"F{len(refs) + 1}"
                refs[ref] = entry.url
                about = [f"source: {entry.source_id}"]
                if entry.significance:
                    about.append(f"significance {entry.significance}")
                if entry.horizon:
                    about.append(f"horizon {entry.horizon}")
                note = forward_notes.get(entry.finding_id)
                lines.append(
                    f"  - {ref}: {entry.note} ({'; '.join(about)})" + (f" Forward note: {note}" if note else "")
                )

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks), refs


def resolve_citations(text: str, refs: dict[str, str]) -> str:
    """Turn the model's finding citations into real links; drop anything else.

    ``[phrase](F12)`` becomes a link to F12's URL; a bare ``[F12]`` or
    ``(F12)`` becomes a source link on the domain. A citation of an unknown
    id, or a link to any URL the model was not given, keeps its words and
    loses the link — the model can never publish a URL of its own.

    :param text: The model's text.
    :param refs: ``F<n>`` to URL, for this digest.
    :returns: The text with markdown links to the given URLs only.
    """
    text = _CITATION.sub(lambda m: f"[{m.group(1)}]({refs[m.group(2)]})" if m.group(2) in refs else m.group(1), text)
    text = _BARE_CITATION.sub(
        lambda m: f" ([{display_domain(refs[m.group(1)])}]({refs[m.group(1)]}))" if m.group(1) in refs else "", text
    )
    allowed = set(refs.values())
    return _LINK.sub(lambda m: m.group(0) if m.group(2) in allowed else m.group(1), text)


def newly_converged(cluster_data: dict[str, dict[str, Any]], week: str) -> list[tuple[str, dict[str, Any]]]:
    """Find the clusters that crossed the candidate-trend threshold this week.

    :param cluster_data: Cluster id to ``{theme, cluster, entries, this_week}``.
    :param week: The week label.
    :returns: ``(cluster id, cluster data)`` for each cluster that converged this week.
    """
    return [
        (cid, data)
        for cid, data in cluster_data.items()
        if data["this_week"]
        and is_candidate_trend(data["entries"])
        and not is_candidate_trend([entry for entry in data["entries"] if entry.week < week])
    ]


def _plain(text: str) -> str:
    return text.strip().strip("*#_\"'").strip().rstrip(".")


def compose_digest_markdown(
    week: str,
    themes: list[ThemeDef],
    digest: StoryDigest,
    refs: dict[str, str],
    tips: list[Finding],
    converged: list[tuple[str, dict[str, Any]]],
    total_signals: int,
) -> str:
    """Assemble the digest: bottom line, stories per theme, tips, convergence, quiet themes.

    The budget is enforced here, not trusted to the model: at most
    ``MAX_STORIES_PER_THEME`` stories per theme, stories on unknown themes
    dropped, and a story that ends up citing no finding dropped — a story
    without evidence is not one.

    :param week: The week label.
    :param themes: The themes, in digest order.
    :param digest: The prose call's output.
    :param refs: ``F<n>`` to URL, for this digest.
    :param tips: The week's board-tip findings.
    :param converged: The clusters that crossed the candidate-trend threshold this week.
    :param total_signals: The number of findings this week.
    :returns: The digest markdown.
    """
    by_theme: dict[str, list[tuple[str, str]]] = {}
    for story in digest.stories:
        text = resolve_citations(story.text.strip(), refs)
        if "](http" not in text:
            logger.warning("digest %s: dropped story %r, it cites no finding", week, story.title)
            continue
        by_theme.setdefault(story.theme, []).append((_plain(story.title), text))

    lines = [
        f"# HiPEAC Vision Watch — Week {week}: {_plain(digest.headline) or 'Quiet week'}",
        "",
        resolve_citations(digest.this_week.strip(), refs),
        "",
    ]

    told = 0
    for theme in themes:
        stories = by_theme.get(theme.theme, [])[:MAX_STORIES_PER_THEME]
        if not stories:
            continue
        lines.extend([f"## {theme.heading}", ""])
        for title, text in stories:
            lines.extend([f"**{title}.** {text}", ""])
            told += 1

    if tips:
        lines.extend(["## Board tips", ""])
        lines.extend(f"- _{tip.summary}_ — [{display_domain(tip.url)}]({tip.url})" for tip in tips)
        lines.append("")

    if converged:
        headings = {theme.theme: theme.heading for theme in themes}
        lines.extend(["## Newly converged", ""])
        lines.extend(
            f"- **{data['cluster'].name}** ({headings.get(data['theme'], data['theme'])}): "
            f"{tally_text(data['entries'])}. "
            "Enough independent, sustained evidence to consider naming it in the Vision."
            for _cid, data in converged
        )
        lines.append("")

    quiet = [theme.heading for theme in themes if not by_theme.get(theme.theme)]
    if quiet:
        lines.extend([f"_Quiet this week: {', '.join(quiet)}._", ""])

    lines.append(
        f"_{told} {'story' if told == 1 else 'stories'} from {total_signals} signals this week; "
        f"all signals are listed in {workspace.signals_filename(week)}._"
    )
    return "\n".join(lines) + "\n"


def compose_signals_log(
    week: str, themes: list[ThemeDef], cluster_data: dict[str, dict[str, Any]], findings: list[Finding]
) -> str:
    """List every finding of the week, by theme and story, so the digest can stay short.

    :param week: The week label.
    :param themes: The themes, in digest order.
    :param cluster_data: Cluster id to ``{theme, cluster, entries, this_week}``.
    :param findings: The week's findings.
    :returns: The signals log markdown.
    """
    lines = [
        f"# HiPEAC Vision Watch — all signals, week {week}",
        "",
        f"{len(findings)} findings, by theme and story.",
        "",
    ]
    placed: set[str] = set()

    for theme in themes:
        stories = [data for data in cluster_data.values() if data["theme"] == theme.theme and data["this_week"]]
        if not stories:
            continue
        lines.extend([f"## {theme.heading}", ""])
        for data in sorted(stories, key=lambda d: -len(d["this_week"])):
            lines.extend([f"### {data['cluster'].name} ({tally_text(data['entries'])})", ""])
            for entry in _ranked(data["this_week"]):
                placed.add(entry.finding_id)
                lines.append(f"- [{entry.note or entry.title}]({entry.url}) — {entry.source_id}")
            lines.append("")

    unplaced = [finding for finding in findings if finding.id not in placed]
    if unplaced:
        lines.extend(["## Not in any story", ""])
        lines.extend(f"- [{finding.summary}]({finding.url}) — {finding.source_id}" for finding in unplaced)
        lines.append("")

    return "\n".join(lines)


async def digest_node(
    state: VisionWatchState,
    *,
    services: Services,
    llm: Any,
) -> dict[str, Any]:
    """Compose the week's digest from the cluster logs, write it, send it.

    One prose call writes the stories; code picks the candidates, resolves
    the citations and enforces the budget. The full list of the week's
    findings is written next to the digest as its signals log.

    :param state: The graph state; carries the week and the ``send`` opt-in.
    :param services: The wired services (mail for the send step).
    :param llm: The chat model used for the stories.
    :returns: State updates: digest markdown, sent flag.
    """
    week = state.week

    # Preflight: the digest is write-once, so composing a week that already
    # has one would pay for the prose call and then raise on the write. A
    # recorded digest is still sendable once — compose, review, then --send.
    if recorded := workspace.read_weekly_digest(week):
        logger.info("week %s already has a digest; skipping composition", week)
        return {"digest_markdown": recorded, "digest_sent": await _send(services, state, week, recorded)}

    themes = workspace.read_themes()
    cluster_data = _collect_clusters(week, [theme.theme for theme in themes])
    findings_file = workspace.read_findings_file(week)
    findings = findings_file.findings if findings_file else []

    candidates = story_candidates(week, themes, cluster_data, _catalog())
    forward_notes = {finding.id: finding.forward_note for finding in findings if finding.forward_note}
    material, refs = story_material(themes, candidates, forward_notes)

    if refs:
        digest = await llm.with_structured_output(StoryDigest).ainvoke(DIGEST_STORIES + "\n\n" + material)
    else:
        digest = QUIET_WEEK

    tips = [finding for finding in findings if finding.source_id == "board-tip"]
    markdown = compose_digest_markdown(
        week, themes, digest, refs, tips, newly_converged(cluster_data, week), len(findings)
    )
    workspace.write_weekly_signals(week, compose_signals_log(week, themes, cluster_data, findings))
    workspace.write_weekly_digest(week, markdown)

    return {"digest_markdown": markdown, "digest_sent": await _send(services, state, week, markdown)}


def _subject(markdown: str) -> str:
    """Take the email subject from the digest's title line."""
    first = markdown.splitlines()[0] if markdown else ""
    return first.removeprefix("#").strip() or "HiPEAC Vision Watch"


async def _send(services: Services, state: VisionWatchState, week: str, markdown: str) -> bool:
    """Email a week's digest to the board, at most once and only with ``--send``.

    :param services: The wired services (mail).
    :param state: The graph state; carries the ``send`` opt-in.
    :param week: The week label.
    :param markdown: The digest markdown; its title line is the subject.
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
        subject=_subject(markdown),
        text=markdown,
        html=markdown_to_html(markdown),
        reply_to=watch_settings.HIPEAC_VISION_REPLY_TO,
    )
    workspace.mark_weekly_digest_sent(week, message_id)
    return True


def _catalog() -> SourceCatalog:
    """Read the source catalog, for the ranking's independence discount."""
    return workspace.read_source_catalog()
