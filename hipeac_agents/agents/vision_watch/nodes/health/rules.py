"""Judgement-free source-health rules: label each source from its recent weeks."""

from typing import NamedTuple

from hipeac_agents.agents.vision_watch.schemas import FindingsFile, HealthLabel, RejectedFile, SourceReport


# A source must look stale or silent this many weeks in a row before it is
# flagged: one quiet week is normal, three is a broken source.
STREAK_WEEKS = 3

# Most urgent first; also the report's section order.
LABEL_ORDER: tuple[HealthLabel, ...] = (
    "fetch_failed",
    "empty_feed",
    "truncated_feed",
    "stale_listing",
    "silent",
    "skipped",
)

LABEL_HINTS: dict[HealthLabel, str] = {
    "fetch_failed": "the feed or page could not be fetched — check the URL",
    "empty_feed": "the feed returned no entries — the feed URL is probably dead or moved",
    "truncated_feed": "the feed no longer reaches back to Saturday — run `snapshot-feeds` daily",
    "stale_listing": f"only out-of-window items for {STREAK_WEEKS} weeks — the listing page is stale or misread",
    "silent": f"no candidates at all for {STREAK_WEEKS} weeks",
    "skipped": "marked bot-protected, never checked — find a feed or drop it",
}


class WeekActivity(NamedTuple):
    """One source's footprint in one week's evidence."""

    verified: int
    rejected: int
    reasons: frozenset[str]


QUIET = WeekActivity(0, 0, frozenset())


def activity_by_source(findings: FindingsFile | None, rejected: RejectedFile | None) -> dict[str, WeekActivity]:
    """Tally each source's findings and rejects in one week's evidence.

    :param findings: The week's findings file, if any.
    :param rejected: The week's rejected file, if any.
    :returns: Source id to its activity that week.
    """
    verified: dict[str, int] = {}
    rejects: dict[str, int] = {}
    reasons: dict[str, set[str]] = {}
    for finding in findings.findings if findings else []:
        verified[finding.source_id] = verified.get(finding.source_id, 0) + 1
    for item in rejected.rejected if rejected else []:
        rejects[item.source_id] = rejects.get(item.source_id, 0) + 1
        reasons.setdefault(item.source_id, set()).add(item.reason)
    return {
        source_id: WeekActivity(
            verified.get(source_id, 0), rejects.get(source_id, 0), frozenset(reasons.get(source_id, ()))
        )
        for source_id in verified.keys() | rejects.keys()
    }


def label_source(report: SourceReport, previous: list[WeekActivity]) -> HealthLabel:
    """Label one source from this week's report and its previous weeks.

    :param report: The source's report for this week.
    :param previous: Its activity in the preceding weeks, most recent first.
    :returns: The health label.
    """
    if report.status == "blocked":
        return "skipped"
    if report.status == "failed" or "feed_fetch_failed" in report.flags:
        return "fetch_failed"
    if "feed_empty" in report.flags:
        return "empty_feed"
    if "feed_truncated" in report.flags:
        return "truncated_feed"

    weeks = [WeekActivity(report.verified, report.rejected, frozenset(report.reasons)), *previous]
    if len(weeks) < STREAK_WEEKS:
        return "ok"
    streak = weeks[:STREAK_WEEKS]
    if all(w.verified == 0 and w.rejected > 0 and w.reasons == {"out_of_window"} for w in streak):
        return "stale_listing"
    if all(w.verified == 0 and w.rejected == 0 for w in streak):
        return "silent"
    return "ok"


def unhealthy(labels: dict[str, HealthLabel]) -> dict[str, HealthLabel]:
    """Keep only the sources that need attention.

    :param labels: Source id to label.
    :returns: The non-``ok`` labels.
    """
    return {source_id: label for source_id, label in labels.items() if label != "ok"}


def render_health_markdown(
    week: str, labels: dict[str, HealthLabel], reports: list[SourceReport], changed: bool
) -> str:
    """Render a week's source-health report.

    :param week: The week label.
    :param labels: Source id to label, for every checked catalog source.
    :param reports: The week's source reports, for their details.
    :param changed: Whether the set of unhealthy sources changed since the last report.
    :returns: The report markdown.
    """
    details = {r.source_id: r.detail for r in reports}
    attention = unhealthy(labels)
    lines = [
        f"# vision-watch source health — {week}",
        "",
        f"{len(attention)} of {len(labels)} sources need attention"
        + (" (changed since the last report)." if changed else " (unchanged since the last report)."),
        "",
    ]
    for label in LABEL_ORDER:
        sources = sorted(source_id for source_id, value in attention.items() if value == label)
        if not sources:
            continue
        lines.extend([f"## {label} ({len(sources)})", "", f"_{LABEL_HINTS[label]}_", ""])
        lines.extend(
            f"- {source_id}" + (f" — {details[source_id]}" if details.get(source_id) else "") for source_id in sources
        )
        lines.append("")
    return "\n".join(lines)
