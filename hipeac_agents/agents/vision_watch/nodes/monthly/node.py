"""The monthly digest node: where the open questions stand, from the month's weekly ledgers."""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from hipeac_agents.agents.vision_watch import settings as watch_settings
from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.cadence import last_closed_window, week_window, weekly_label
from hipeac_agents.agents.vision_watch.nodes.digest.node import NEW_TOPIC, resolve_citations
from hipeac_agents.agents.vision_watch.schemas import LedgerEntry, LedgerFile, ThemeDef
from hipeac_agents.services.factory import Services
from hipeac_agents.services.mail import markdown_to_html

from .models import MonthlyDigest, monthly_model
from .prompts import MONTHLY_QUESTIONS


logger = logging.getLogger(__name__)

NOTHING_QUALIFIES = "Nothing reached the evidence gate this month: no open question or new topic kept recurring."

# The evidence gate: a question gets an answer only when its signals recur.
# A looser gate (two weeks, or one signal past early) let 22-33 of the 42
# questions through each month and the digest ran to 3,300-3,700 words;
# requiring a signal past early instead of a third signal kept 2-signal
# questions whose draft positions came out generic.
MIN_SIGNALS = 3
MIN_WEEKS = 2
TOPIC_MIN_SIGNALS = 3
TOPIC_CONVERGED_MIN_SIGNALS = 2  # a new topic whose story is a candidate trend

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def month_weeks(month: str) -> set[str]:
    """Week labels of the weeks with most of their days in a calendar month.

    A week belongs to the month of its Thursday, as ISO does for years, so a
    week is never split between two months.

    :param month: A calendar month as ``"YYYY-MM"``.
    :returns: Week labels such as ``{"2026-W27", ..., "2026-W31"}``.
    """
    year, mon = (int(part) for part in month.split("-"))
    first = date(year, mon, 1)
    thursday = first + timedelta(days=(3 - first.weekday()) % 7)
    weeks: set[str] = set()

    while thursday.month == mon:
        weeks.add(weekly_label(thursday))
        thursday += timedelta(days=7)

    return weeks


def month_is_complete(month: str, today: date) -> bool:
    """Tell whether every week of a month has closed.

    :param month: A calendar month as ``"YYYY-MM"``.
    :param today: The day of the run.
    :returns: ``True`` once the month's last week has closed.
    """
    return week_window(max(month_weeks(month)))[1] < today


def last_complete_month(today: date) -> str:
    """Return the latest month whose weeks have all closed.

    The last closed week ends its month when the next week's Thursday is in
    another month; otherwise its month is still running and the month before
    is the latest complete one.

    :param today: The day of the run.
    :returns: A calendar month as ``"YYYY-MM"``, e.g. ``"2026-09"`` on 5 October 2026.
    """
    monday, _sunday = last_closed_window(today)
    thursday = monday + timedelta(days=3)
    if (thursday + timedelta(days=7)).month == thursday.month:
        thursday = thursday.replace(day=1) - timedelta(days=1)
    return f"{thursday.year}-{thursday.month:02d}"


@dataclass(frozen=True)
class Signal:
    """One printed weekly item, with the week it was printed in."""

    week: str
    entry: LedgerEntry


def weeks_of(signals: list[Signal]) -> int:
    """Count the distinct weeks a list of signals spans.

    :param signals: The signals.
    :returns: The number of weeks.
    """
    return len({signal.week for signal in signals})


@dataclass
class Gate:
    """The month's evidence, sorted by the gate: what the prose call sees and what it never does."""

    questions: dict[str, list[Signal]] = field(default_factory=dict)
    topics: dict[str, list[Signal]] = field(default_factory=dict)
    thin: dict[str, list[Signal]] = field(default_factory=dict)
    no_evidence: list[str] = field(default_factory=list)
    earlier: dict[tuple[str, str], list[Signal]] = field(default_factory=dict)


def _qualifies(signals: list[Signal]) -> bool:
    return len(signals) >= MIN_SIGNALS and weeks_of(signals) >= MIN_WEEKS


def _topic_qualifies(signals: list[Signal]) -> bool:
    converged = any(signal.entry.status == "candidate-trend" for signal in signals)
    return len(signals) >= (TOPIC_CONVERGED_MIN_SIGNALS if converged else TOPIC_MIN_SIGNALS)


def _most_evidence(items: dict[str, list[Signal]]) -> dict[str, list[Signal]]:
    # Stable: equal counts keep theme and question order.
    return dict(sorted(items.items(), key=lambda item: (-len(item[1]), -weeks_of(item[1]))))


def evidence_gate(ledgers: list[LedgerFile], themes: list[ThemeDef]) -> Gate:
    """Sort the month's signals by the evidence gate, in plain code.

    A question qualifies with ``MIN_SIGNALS`` signals across ``MIN_WEEKS``
    weeks; one with fewer is thin evidence. A signal counts only while its
    question's text is unchanged; signals on a reworded or removed question
    are "earlier questions". A NEW topic qualifies with ``TOPIC_MIN_SIGNALS``
    signals on its story, or ``TOPIC_CONVERGED_MIN_SIGNALS`` once the story
    is a candidate trend.

    :param ledgers: The month's weekly ledgers.
    :param themes: The themes, in digest order.
    :returns: The gate; qualifying questions and topics most evidence first
        (signals, then weeks), the rest in theme and question order.
    """
    questions = {qid: question for theme in themes for qid, question in theme.questions_by_id.items()}
    counted: dict[str, list[Signal]] = {qid: [] for qid in questions}
    topics: dict[str, list[Signal]] = {}
    earlier: dict[tuple[str, str], list[Signal]] = {}

    for ledger in sorted(ledgers, key=lambda ledger: ledger.week):
        for entry in ledger.entries:
            signal = Signal(week=ledger.week, entry=entry)
            if entry.question_id == NEW_TOPIC:
                topics.setdefault(entry.cluster_id, []).append(signal)
            elif questions.get(entry.question_id) == entry.question:
                counted[entry.question_id].append(signal)
            else:
                earlier.setdefault((entry.question_id, entry.question), []).append(signal)

    return Gate(
        questions=_most_evidence({qid: signals for qid, signals in counted.items() if signals and _qualifies(signals)}),
        topics=_most_evidence({cid: signals for cid, signals in topics.items() if _topic_qualifies(signals)}),
        thin={qid: signals for qid, signals in counted.items() if signals and not _qualifies(signals)},
        no_evidence=[qid for qid, signals in counted.items() if not signals],
        earlier=earlier,
    )


@dataclass
class Material:
    """The prose call's input and what code needs to check its answer."""

    text: str
    refs: dict[str, str] = field(default_factory=dict)
    topics: dict[str, str] = field(default_factory=dict)


def monthly_material(themes: list[ThemeDef], gate: Gate) -> Material:
    """Render the prose call's input: each qualifying question and topic with its signals.

    The signals' links become finding keys (F1, F2, ...), so the model cites
    by key and never writes a URL.

    :param themes: The themes, in digest order.
    :param gate: The month's gate.
    :returns: The material; ``refs`` maps each ``F<n>`` to its URL, ``topics`` each ``T<n>`` to its cluster.
    """
    material = Material(text="")
    headings = {theme.theme: theme.heading for theme in themes}
    questions = {qid: question for theme in themes for qid, question in theme.questions_by_id.items()}
    keys: dict[str, str] = {}

    def keyed(match: re.Match[str]) -> str:
        url = match.group(2)
        if url not in keys:
            keys[url] = f"F{len(keys) + 1}"
            material.refs[keys[url]] = url
        return f"[{match.group(1)}]({keys[url]})"

    def signal_lines(signals: list[Signal]) -> list[str]:
        return [
            f"  - {_short_week(signal.week)} ({signal.entry.status}{', early' if signal.entry.early else ''}; "
            f"lean: {signal.entry.lean}) {signal.entry.title}: {_LINK.sub(keyed, signal.entry.text)}"
            for signal in signals
        ]

    blocks: list[str] = []
    for qid, signals in gate.questions.items():
        theme = qid.rsplit(".", 1)[0]
        lines = [f"QUESTION {qid} (line: {headings.get(theme, theme)}): {questions[qid]}"]
        blocks.append("\n".join(lines + signal_lines(signals)))

    for cluster_id, signals in gate.topics.items():
        key = f"T{len(material.topics) + 1}"
        material.topics[key] = cluster_id
        latest = signals[-1].entry
        lines = [f"TOPIC {key} (line: {headings.get(latest.theme, latest.theme)}; {latest.status}): {latest.lean}"]
        blocks.append("\n".join(lines + signal_lines(signals)))

    material.text = "\n\n".join(blocks)
    return material


def _short_week(week: str) -> str:
    return week.rsplit("-", 1)[-1]


def _counts(signals: list[Signal]) -> str:
    weeks = weeks_of(signals)
    return f"{len(signals)} signal{'s' if len(signals) != 1 else ''} in {weeks} week{'s' if weeks != 1 else ''}"


def _plain(text: str) -> str:
    return text.strip().strip("*#_\"'").strip().rstrip(".")


def compose_monthly_markdown(
    month: str,
    themes: list[ThemeDef],
    gate: Gate,
    digest: MonthlyDigest | None,
    material: Material,
    missing_weeks: list[str],
) -> str:
    """Assemble the monthly digest: where the questions stand, new topics, thin and missing evidence.

    The rules are enforced here, not trusted to the model: answers and
    topics that did not pass the gate are dropped, counts come from the
    ledgers, and questions are ordered by evidence.

    :param month: The calendar month as ``"YYYY-MM"``.
    :param themes: The themes, in digest order.
    :param gate: The month's gate.
    :param digest: The prose call's output, or ``None`` when nothing qualified.
    :param material: The prose call's input, for citations and topic keys.
    :param missing_weeks: The month's weeks without a ledger.
    :returns: The monthly digest markdown.
    """
    headings = {theme.theme: theme.heading for theme in themes}
    questions = {qid: question for theme in themes for qid, question in theme.questions_by_id.items()}

    def heading_of(qid: str) -> str:
        theme = qid.rsplit(".", 1)[0]
        return headings.get(theme, theme)

    answers = {}
    topics = {}
    for answer in digest.answers if digest else []:
        if answer.question not in gate.questions or answer.question in answers:
            logger.warning("monthly %s: dropped answer for unqualified or repeated %r", month, answer.question)
        else:
            answers[answer.question] = answer
    for topic in digest.new_topics if digest else []:
        if topic.topic not in material.topics or topic.topic in topics:
            logger.warning("monthly %s: dropped unqualified or repeated topic %r", month, topic.topic)
        else:
            topics[topic.topic] = topic

    lines = [
        f"# HiPEAC Vision Watch — {month}",
        "",
        "## Bottom line",
        "",
        resolve_citations(digest.bottom_line.strip(), material.refs) if digest else NOTHING_QUALIFIES,
        "",
        "## Where the questions stand",
        "",
    ]

    if not gate.questions:
        lines.extend(["_No open question qualified this month._", ""])

    for qid, signals in gate.questions.items():
        lines.extend([f"### {questions[qid]}", ""])
        answer = answers.get(qid)
        if answer is None:
            lines.extend([f"_{heading_of(qid)} · {_counts(signals)}_", ""])
            lines.extend(f"- {signal.week}: {signal.entry.text}" for signal in signals)
            lines.append("")
            continue
        lines.extend(
            [
                f"_{heading_of(qid)} · {_plain(answer.lean)} · {_counts(signals)}_",
                "",
                resolve_citations(answer.evidence.strip(), material.refs),
                "",
                f"**For 2027:** {answer.for_2027.strip()}",
                "",
                f"**Still open:** {answer.still_open.strip()}",
                "",
            ]
        )

    if topics:
        lines.extend(["## New for the board", ""])
        for key, cluster_id in material.topics.items():
            if key not in topics:
                continue
            signals = gate.topics[cluster_id]
            latest = signals[-1].entry
            lines.extend(
                [
                    f"### {_plain(topics[key].title)}",
                    "",
                    f"_{headings.get(latest.theme, latest.theme)} · {_counts(signals)}"
                    f"{' · candidate trend' if latest.status == 'candidate-trend' else ''}_",
                    "",
                    resolve_citations(topics[key].evidence.strip(), material.refs),
                    "",
                    f"**A question to add:** {topics[key].proposed_question.strip()}",
                    "",
                ]
            )

    if gate.thin:
        lines.extend(["## Thin evidence", "", "Too few signals to call yet:", ""])
        for theme in themes:
            thin = [
                f"{questions[qid]} ({_counts(signals)})"
                for qid, signals in gate.thin.items()
                if qid.rsplit(".", 1)[0] == theme.theme
            ]
            if thin:
                lines.append(f"- **{theme.heading}:** {' · '.join(thin)}")
        lines.append("")

    if gate.no_evidence:
        lines.extend(["## No evidence this month", ""])
        for theme in themes:
            unanswered = [questions[qid] for qid in gate.no_evidence if qid.rsplit(".", 1)[0] == theme.theme]
            if unanswered:
                lines.append(f"- **{theme.heading}:** {' · '.join(unanswered)}")
        lines.append("")

    if gate.earlier:
        lines.extend(["## Earlier questions", "", "Signals on questions since reworded or removed:", ""])
        lines.extend(f'- "{text}" ({qid}): {_counts(signals)}' for (qid, text), signals in gate.earlier.items())
        lines.append("")

    total = sum(len(signals) for group in (gate.questions, gate.topics, gate.thin) for signals in group.values())
    lines.append(
        f"_{len(gate.questions)} of {len(questions)} open questions qualified and {len(topics)} new "
        f"topic{'s' if len(topics) != 1 else ''}, from {total} signals in the weekly digests"
        + (f"; no ledger for {', '.join(missing_weeks)}" if missing_weeks else "")
        + "._"
    )
    return "\n".join(lines) + "\n"


async def monthly_node(
    state: Any,
    *,
    services: Services,
    llm: Any,
) -> dict[str, Any]:
    """Compose the month's digest from the weekly ledgers and write it.

    Code sorts the month's signals by the evidence gate; one prose call
    writes where each qualifying question stands, the qualifying new topics
    and the bottom line. No call when nothing qualifies. Writes
    ``digests/monthly/digest-YYYY-MM.md``.

    :param state: The graph state; carries ``month``.
    :param services: The wired services (mail for the send step).
    :param llm: The chat model used for the prose call.
    :returns: State updates: digest markdown, sent flag.
    """
    month = state.month

    # Preflight: the monthly digest is write-once, so composing a month that
    # already has one would pay for the prose call and then raise on the
    # write. A recorded digest is still sendable once.
    if recorded := workspace.read_monthly_digest(month):
        logger.info("month %s already has a digest; skipping synthesis", month)
        sent = await _send(services, state, month, recorded, _recorded_bottom_line(recorded))
        return {"digest_markdown": recorded, "digest_sent": sent}

    themes = workspace.read_themes()
    weeks = sorted(month_weeks(month))
    ledgers = {week: ledger for week in weeks if (ledger := workspace.read_weekly_ledger(week))}
    gate = evidence_gate(list(ledgers.values()), themes)
    material = monthly_material(themes, gate)

    digest = None
    if gate.questions or gate.topics:
        schema = monthly_model(list(gate.questions), list(material.topics))
        digest = await llm.with_structured_output(schema).ainvoke(MONTHLY_QUESTIONS + "\n\n" + material.text)

    markdown = compose_monthly_markdown(
        month, themes, gate, digest, material, [week for week in weeks if week not in ledgers]
    )
    workspace.write_monthly_digest(month, markdown)

    sent = await _send(services, state, month, markdown, digest.bottom_line if digest else NOTHING_QUALIFIES)
    return {"digest_markdown": markdown, "digest_sent": sent}


def _recorded_bottom_line(markdown: str) -> str:
    """Recover the Bottom line text from a recorded monthly digest.

    :param markdown: The recorded digest.
    :returns: The first paragraph under "## Bottom line", or ``""``.
    """
    _, _, after = markdown.partition("## Bottom line")
    return next((block.strip() for block in after.split("\n\n") if block.strip()), "")


async def _send(services: Services, state: Any, month: str, markdown: str, bottom_line: str) -> bool:
    """Email a month's digest to the board, at most once and only with ``--send``.

    :param services: The wired services (mail).
    :param state: The graph state; carries the ``send`` opt-in.
    :param month: The calendar month as ``"YYYY-MM"``.
    :param markdown: The digest markdown.
    :param bottom_line: The Bottom line text; its first 100 characters are the subject.
    :returns: ``True`` when the digest was sent by this run.
    """
    recipient = watch_settings.HIPEAC_VISION_BOARD_EMAIL
    inbox = watch_settings.AGENTMAIL_INBOX_VISION_WATCH

    if not (state.send and services.mail is not None and inbox and recipient):
        return False
    if workspace.monthly_digest_sent(month):
        logger.info("month %s digest was already sent; not sending again", month)
        return False

    message_id = await services.mail.send(
        inbox,
        recipient,
        subject=bottom_line[:100],
        text=markdown,
        html=markdown_to_html(markdown),
        reply_to=watch_settings.HIPEAC_VISION_REPLY_TO,
    )
    workspace.mark_monthly_digest_sent(month, message_id)
    return True
