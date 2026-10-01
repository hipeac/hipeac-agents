"""The digest node's orchestration: story selection, one prose call, assembly, write, send."""

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from hipeac_agents.agents.vision_watch import settings as watch_settings
from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.cluster.tallies import (
    entries_through,
    is_candidate_trend,
    log_with_current_classes,
    sort_lead_candidates,
    tally_text,
    trend_status,
)
from hipeac_agents.agents.vision_watch.schemas import (
    ClusterEntry,
    Finding,
    LedgerEntry,
    LedgerFile,
    SourceCatalog,
    ThemeDef,
)
from hipeac_agents.agents.vision_watch.state import VisionWatchState
from hipeac_agents.services.factory import Services
from hipeac_agents.services.mail import markdown_to_html
from hipeac_agents.services.urls import display_domain
from hipeac_agents.storage import WorkspaceError

from .models import DigestItem, WeeklyDigest, WeeklyIntro
from .prompts import DIGEST_INTRO, DIGEST_STORIES


logger = logging.getLogger(__name__)

# The digest's budget: at most this many full stories per theme; the theme's
# other candidates that move an answer follow as one-line items, so every
# question that moved stays visible. Everything is kept in the signals log.
MAX_STORIES_PER_THEME = 2
STORY_CANDIDATES_PER_THEME = 4
FINDINGS_PER_STORY = 4

QUIET_WEEK = WeeklyDigest(headline="Quiet week", this_week="No new signals reached the watch this week.")
NEW_TOPIC = "NEW"

_CITATION = re.compile(r"\[([^\]]+)\]\((F\d+)\)")
_BARE_CITATION = re.compile(r"\s*[\[(](F\d+)[\])]")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _collect_clusters(week: str, themes: list[str], catalog: SourceCatalog) -> dict[str, dict[str, Any]]:
    """Collect every cluster of the themes, scoped through this week.

    Entries recorded after ``week`` are excluded, so a digest re-composed
    later for the same week sees the same tallies. Entries carry their
    source's class as of the current catalog.

    :param week: The week label.
    :param themes: The theme ids, in digest order.
    :param catalog: The source catalog, for the entries' current classes.
    :returns: Cluster id to ``{theme, cluster, entries, this_week}``.
    """
    cluster_data: dict[str, dict[str, Any]] = {}

    for theme in themes:
        log = workspace.read_cluster_log(theme)

        if log is None:
            continue

        log = log_with_current_classes(log, catalog)

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

    Ranked by ``sort_lead_candidates`` — novelty, then this week's reach —
    and cut to ``STORY_CANDIDATES_PER_THEME``.

    :param week: The week label.
    :param themes: The themes, in digest order.
    :param cluster_data: Cluster id to ``{theme, cluster, entries, this_week}``.
    :param catalog: The source catalog, for the primary-source rule.
    :returns: Theme id to ``(cluster id, cluster data)`` pairs.
    """
    touched = {cid: data for cid, data in cluster_data.items() if data["this_week"]}
    candidates: dict[str, list[tuple[str, dict[str, Any]]]] = {}

    for theme in themes:
        mine = [(d["cluster"], d["entries"], d["this_week"]) for d in touched.values() if d["theme"] == theme.theme]
        ranked = sort_lead_candidates(mine, week, catalog)[:STORY_CANDIDATES_PER_THEME]
        candidates[theme.theme] = [(cluster.id, touched[cluster.id]) for cluster, _, _ in ranked]

    return candidates


@dataclass(frozen=True)
class StoryRef:
    """A candidate story as the prose call sees it: its theme, cluster and derived status."""

    theme: str
    cluster_id: str
    status: str


@dataclass
class Material:
    """The prose call's input and what code needs to check its answer."""

    text: str
    refs: dict[str, str] = field(default_factory=dict)
    finding_ids: dict[str, str] = field(default_factory=dict)
    stories: dict[str, StoryRef] = field(default_factory=dict)


def story_material(
    themes: list[ThemeDef],
    candidates: dict[str, list[tuple[str, dict[str, Any]]]],
    forward_notes: dict[str, str],
    catalog: SourceCatalog,
) -> Material:
    """Render the prose call's input: each theme's open questions by id, then its keyed candidates.

    :param themes: The themes, in digest order.
    :param candidates: Theme id to its candidate stories.
    :param forward_notes: Finding id to its forward note, when it has one.
    :param catalog: The source catalog, for each story's trend status.
    :returns: The material; ``refs`` maps each ``F<n>`` to the finding's URL,
        ``finding_ids`` each URL to its finding id, ``stories`` each ``S<n>`` to its cluster.
    """
    material = Material(text="")
    blocks: list[str] = []

    for theme in themes:
        lines = [f'THEME "{theme.theme}" ({theme.heading}) — {theme.description.strip()}']
        lines.extend(f"Open question {qid}: {question}" for qid, question in theme.questions_by_id.items())

        stories = candidates.get(theme.theme, [])
        if not stories:
            lines.append("(no stories this week)")

        for cluster_id, data in stories:
            key = f"S{len(material.stories) + 1}"
            status = trend_status(data["entries"], catalog)
            material.stories[key] = StoryRef(theme=theme.theme, cluster_id=cluster_id, status=status)
            lines.append(
                f'{key} Story "{data["cluster"].name}" — {status}; '
                f"{tally_text(data['entries'])}; {len(data['this_week'])} new this week"
            )
            for entry in _ranked(data["this_week"])[:FINDINGS_PER_STORY]:
                ref = f"F{len(material.refs) + 1}"
                material.refs[ref] = entry.url
                material.finding_ids[entry.url] = entry.finding_id
                # No significance: the prose call weighs the evidence itself,
                # unanchored by the small model's scores.
                about = [f"source: {entry.source_id}"]
                if entry.horizon:
                    about.append(f"horizon {entry.horizon}")
                note = forward_notes.get(entry.finding_id)
                lines.append(
                    f"  - {ref}: {entry.note} ({'; '.join(about)})" + (f" Forward note: {note}" if note else "")
                )

        blocks.append("\n".join(lines))

    material.text = "\n\n".join(blocks)
    return material


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
    text = _CITATION.sub(
        lambda m: f"[{m.group(1).strip()}]({refs[m.group(2)]})" if m.group(2) in refs else m.group(1).strip(), text
    )
    text = _BARE_CITATION.sub(
        lambda m: f" ([{display_domain(refs[m.group(1)])}]({refs[m.group(1)]}))" if m.group(1) in refs else "", text
    )
    allowed = set(refs.values())
    return _LINK.sub(lambda m: m.group(0) if m.group(2) in allowed else m.group(1), text)


def newly_converged(
    cluster_data: dict[str, dict[str, Any]], week: str, catalog: SourceCatalog
) -> list[tuple[str, dict[str, Any]]]:
    """Find the clusters that crossed the candidate-trend threshold this week.

    :param cluster_data: Cluster id to ``{theme, cluster, entries, this_week}``.
    :param week: The week label.
    :param catalog: The source catalog, for the primary-source rule.
    :returns: ``(cluster id, cluster data)`` for each cluster that converged this week.
    """
    return [
        (cid, data)
        for cid, data in cluster_data.items()
        if data["this_week"]
        and is_candidate_trend(data["entries"], catalog)
        and not is_candidate_trend([entry for entry in data["entries"] if entry.week < week], catalog)
    ]


def _plain(text: str) -> str:
    return text.strip().strip("*#_\"'").strip().rstrip(".")


def _one_paragraph(text: str) -> str:
    """Collapse the model's line breaks, so the bottom line stays one line of the digest."""
    return " ".join(text.split())


@dataclass
class _Printed:
    item: DigestItem
    ref: StoryRef
    text: str
    urls: list[str]
    also_in: str = ""


def _checked_items(week: str, digest: WeeklyDigest, material: Material, questions: dict[str, str]) -> list[_Printed]:
    """Keep the items code can stand behind: known story and question, first use of a story, cited evidence."""
    kept: list[_Printed] = []
    used: set[str] = set()
    for item in digest.items:
        ref = material.stories.get(item.story)
        text = resolve_citations(item.text.strip(), material.refs)
        urls = list(dict.fromkeys(url for _phrase, url in _LINK.findall(text)))
        if ref is None or item.story in used:
            logger.warning("digest %s: dropped item %r, unknown or repeated story %r", week, item.title, item.story)
        elif item.question != NEW_TOPIC and item.question not in questions:
            logger.warning("digest %s: dropped item %r, unknown question %r", week, item.title, item.question)
        elif not urls:
            logger.warning("digest %s: dropped item %r, it cites no finding", week, item.title)
        else:
            used.add(item.story)
            kept.append(_Printed(item=item, ref=ref, text=text, urls=urls))
    return kept


def _by_theme(themes: list[ThemeDef], items: list[_Printed]) -> dict[str, tuple[list[_Printed], list[_Printed]]]:
    """Place items under their story's theme: full stories within budget, then short items.

    A finding may appear in several themes when it answers a different question
    in each (marked "also in"); an item that repeats earlier findings on the
    same question is an echo and is dropped.
    """
    headings = {theme.theme: theme.heading for theme in themes}
    first_theme: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    placed: dict[str, tuple[list[_Printed], list[_Printed]]] = {}

    for theme in themes:
        mine = [p for p in items if p.ref.theme == theme.theme]
        full = [p for p in mine if not p.item.brief][:MAX_STORIES_PER_THEME]
        ordered = full + [p for p in mine if p not in full]
        kept_full, kept_brief = [], []
        for printed in ordered:
            if all((printed.item.question, url) in seen for url in printed.urls):
                continue
            earlier = [first_theme[url] for url in printed.urls if first_theme.get(url, theme.theme) != theme.theme]
            printed.also_in = headings.get(earlier[0], earlier[0]) if earlier else ""
            seen.update((printed.item.question, url) for url in printed.urls)
            for url in printed.urls:
                first_theme.setdefault(url, theme.theme)
            (kept_full if printed in full else kept_brief).append(printed)
        if kept_full or kept_brief:
            placed[theme.theme] = (kept_full, kept_brief)
    return placed


def _tag(printed: _Printed, questions: dict[str, str], *, full: bool) -> str:
    item = printed.item
    lean = _plain(item.lean)
    tag = f"new topic: {lean}" if item.question == NEW_TOPIC else f"{questions[item.question]} → {lean}"
    # Only full stories carry the label: most one-liners come from emerging
    # clusters, and labelling them all would drown it. The ledger keeps it.
    if full and printed.ref.status == "emerging":
        tag += " · early signal"
    if printed.also_in:
        tag += f" · also in {printed.also_in}"
    return tag


def compose_digest_markdown(
    week: str,
    themes: list[ThemeDef],
    digest: WeeklyDigest,
    material: Material,
    tips: list[Finding],
    converged: list[tuple[str, dict[str, Any]]],
    total_signals: int,
) -> tuple[str, LedgerFile]:
    """Assemble the digest and its ledger: bottom line, tagged items per theme, tips, convergence, quiet themes.

    The rules are enforced here, not trusted to the model: unknown stories
    and questions dropped, an item citing no finding dropped, at most
    ``MAX_STORIES_PER_THEME`` full stories per theme, echoes dropped, and the
    early-signal label taken from the story's derived status (printed on full
    stories only; the ledger flags every item).

    :param week: The week label.
    :param themes: The themes, in digest order.
    :param digest: The prose call's output.
    :param material: The prose call's input, for citations, story keys and finding ids.
    :param tips: The week's board-tip findings.
    :param converged: The clusters that crossed the candidate-trend threshold this week.
    :param total_signals: The number of findings this week.
    :returns: ``(markdown, ledger)`` — the ledger lists every printed item.
    """
    questions = {qid: question for theme in themes for qid, question in theme.questions_by_id.items()}
    placed = _by_theme(themes, _checked_items(week, digest, material, questions))
    ledger = LedgerFile(week=week, created=date.today())

    lines = [
        f"# HiPEAC Vision Watch — Week {week}: {_plain(digest.headline) or 'Quiet week'}",
        "",
        resolve_citations(_one_paragraph(digest.this_week), material.refs),
        "",
    ]

    stories = briefs = 0
    for theme in themes:
        if theme.theme not in placed:
            continue
        full, brief = placed[theme.theme]
        lines.extend([f"## {theme.heading}", ""])
        for printed in full:
            lines.extend(
                [f"**{_plain(printed.item.title)}.** {printed.text}", f"_{_tag(printed, questions, full=True)}_", ""]
            )
        if brief:
            lines.extend(["Also moving:", ""])
            lines.extend(f"- {printed.text} _({_tag(printed, questions, full=False)})_" for printed in brief)
            lines.append("")
        stories += len(full)
        briefs += len(brief)
        ledger.entries.extend(
            LedgerEntry(
                question_id=printed.item.question,
                question=questions.get(printed.item.question, ""),
                lean=_plain(printed.item.lean),
                theme=theme.theme,
                cluster_id=printed.ref.cluster_id,
                status=printed.ref.status,
                early=printed.ref.status == "emerging",
                finding_ids=[material.finding_ids[url] for url in printed.urls if url in material.finding_ids],
                title=_plain(printed.item.title),
                text=printed.text,
            )
            for printed in full + brief
        )

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

    quiet = [theme.heading for theme in themes if theme.theme not in placed]
    if quiet:
        lines.extend([f"_Quiet this week: {', '.join(quiet)}._", ""])

    lines.append(
        f"_{stories} {'story' if stories == 1 else 'stories'} and {briefs} short "
        f"{'item' if briefs == 1 else 'items'} from {total_signals} signals this week; "
        f"all signals are listed in {workspace.signals_filename(week)}._"
    )
    return "\n".join(lines) + "\n", ledger


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

    One prose call tags each candidate with the open question it moves; code
    picks the candidates, checks the tags, resolves the citations and enforces
    the budget. The week's ledger (every printed item) and signals log (every
    finding) are written next to the digest.

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

    themes, catalog, cluster_data, findings, material = _week_material(week)

    if material.refs:
        digest = await llm.with_structured_output(WeeklyDigest).ainvoke(DIGEST_STORIES + "\n\n" + material.text)
    else:
        digest = QUIET_WEEK

    tips = [finding for finding in findings if finding.source_id == "board-tip"]
    markdown, ledger = compose_digest_markdown(
        week, themes, digest, material, tips, newly_converged(cluster_data, week, catalog), len(findings)
    )
    workspace.write_weekly_signals(week, compose_signals_log(week, themes, cluster_data, findings))
    workspace.write_weekly_ledger(ledger)
    workspace.write_weekly_digest(week, markdown)

    return {"digest_markdown": markdown, "digest_sent": await _send(services, state, week, markdown)}


def _week_material(
    week: str,
) -> tuple[list[ThemeDef], SourceCatalog, dict[str, dict[str, Any]], list[Finding], Material]:
    """Rebuild a week's prose-call material from the workspace.

    Scoped through the week, so a later call gets the same story keys and
    finding ids as the one that composed the digest.

    :param week: The week label.
    :returns: ``(themes, catalog, cluster data, findings, material)``.
    """
    themes = workspace.read_themes()
    catalog = workspace.read_source_catalog()
    cluster_data = _collect_clusters(week, [theme.theme for theme in themes], catalog)
    findings_file = workspace.read_findings_file(week)
    findings = findings_file.findings if findings_file else []

    candidates = story_candidates(week, themes, cluster_data, catalog)
    forward_notes = {finding.id: finding.forward_note for finding in findings if finding.forward_note}
    return themes, catalog, cluster_data, findings, story_material(themes, candidates, forward_notes, catalog)


def _digest_lines(markdown: str) -> list[str]:
    """Split a digest into lines, checking its bottom line sits where it is replaced.

    :raises ValueError: If the digest does not start with a title, a blank
        line, the bottom line and a blank line.
    """
    lines = markdown.split("\n")
    if len(lines) < 4 or not lines[0].startswith("# ") or lines[1] or not lines[2].strip() or lines[3]:
        raise ValueError("digest does not start with a title, a blank line, the bottom line and a blank line")
    return lines


def replace_bottom_line(markdown: str, paragraph: str) -> str:
    """Swap a digest's bottom line, leaving every other line as it was.

    The bottom line is the one line between the title and the first section,
    each side a blank line; a digest of any other shape is refused rather
    than guessed at.

    :param markdown: The recorded digest.
    :param paragraph: The new bottom line, already resolved to links.
    :returns: The digest with the new bottom line.
    :raises ValueError: If the digest does not have the expected layout.
    """
    lines = _digest_lines(markdown)
    lines[2] = _one_paragraph(paragraph)
    return "\n".join(lines)


async def intro_node(state: VisionWatchState, *, llm: Any) -> dict[str, Any]:
    """Rewrite a recorded week's bottom line, and nothing else.

    One prose call sees the week's rebuilt material and the digest as
    printed, without its old bottom line, so it cites the same finding ids
    and leads with the stories the board got. The previous digest is backed
    up; the ledger, signals log and sent marker are left alone, and nothing
    is sent. A week without candidate stories is left as it was.

    :param state: The graph state; carries the week.
    :param llm: The chat model used for the bottom line.
    :returns: State updates: the digest markdown.
    :raises WorkspaceError: If the week has no digest.
    :raises ValueError: If the digest does not have the expected layout.
    """
    week = state.week
    recorded = workspace.read_weekly_digest(week)
    if recorded is None:
        raise WorkspaceError(f"no digest for {week}; run weekly-digest first")

    lines = _digest_lines(recorded)
    *_, material = _week_material(week)
    if not material.refs:
        logger.info("week %s has no candidate stories; bottom line left as it was", week)
        return {"digest_markdown": recorded}

    printed = "\n".join([lines[0], *lines[3:]])
    intro = await llm.with_structured_output(WeeklyIntro).ainvoke(
        DIGEST_INTRO + "\n\n" + material.text + "\n\nTHE DIGEST AS PRINTED (without its bottom line):\n\n" + printed
    )
    markdown = replace_bottom_line(recorded, resolve_citations(_one_paragraph(intro.this_week), material.refs))
    backup = workspace.rewrite_weekly_digest(week, markdown)
    logger.info("week %s bottom line rewritten; previous digest in %s", week, backup)
    return {"digest_markdown": markdown}


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
