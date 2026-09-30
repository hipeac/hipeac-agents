"""Judgement-free cluster tallies and the candidate-trend threshold.

Every function here is deterministic Python — unit-tested with no mocking,
no LLM. Everything the digest needs about a cluster is tallied from its log
entries at read time and never stored.
"""

from hipeac_agents.agents.vision_watch import schemas
from hipeac_agents.agents.vision_watch.schemas import Cluster, Finding


# Candidate-trend threshold: at least 4 findings across at least 3 source
# classes over at least 3 distinct weeks, with at least one primary source —
# a story told only by press, analysts and commentators has not converged.
CANDIDATE_TREND_MIN_FINDINGS = 4
CANDIDATE_TREND_MIN_CLASSES = 3
CANDIDATE_TREND_MIN_WEEKS = 3

# The one class for findings from outside the catalog (sweep, inbox, board
# tips) and for entries whose recorded class the catalog no longer declares.
UNLISTED_CLASS = "unlisted"


def current_classes(entries: list[schemas.ClusterEntry], catalog: schemas.SourceCatalog) -> list[schemas.ClusterEntry]:
    """Give each entry its source's class as of the current catalog.

    A reclassified source counts in its new class for every past week, without
    rewriting the append-only logs. A source no longer in the catalog keeps its
    recorded class while the catalog still declares it, otherwise it is unlisted.

    :param entries: The cluster's log entries, as recorded.
    :param catalog: The parsed source catalog.
    :returns: Copies of the entries with their current class; the log on disk is untouched.
    """

    def resolve(entry: schemas.ClusterEntry) -> schemas.ClusterEntry:
        recorded = entry.source_class if entry.source_class in catalog.classes else UNLISTED_CLASS
        source_class = catalog.class_of(entry.source_id) or recorded
        return entry if source_class == entry.source_class else entry.model_copy(update={"source_class": source_class})

    return [resolve(entry) for entry in entries]


def log_with_current_classes(log: schemas.ClusterLog, catalog: schemas.SourceCatalog) -> schemas.ClusterLog:
    """Read a whole cluster log with every entry's class as of the current catalog.

    :param log: The cluster log, as recorded.
    :param catalog: The parsed source catalog.
    :returns: A copy of the log for tallying; never written back.
    """
    clusters = [
        cluster.model_copy(update={"entries": current_classes(cluster.entries, catalog)}) for cluster in log.clusters
    ]
    return log.model_copy(update={"clusters": clusters})


def reach(entries: list[schemas.ClusterEntry]) -> int:
    """Count distinct source classes in a cluster — one class is an echo.

    :param entries: The cluster's log entries.
    :returns: The number of distinct ``source_class`` values.
    """
    return len({entry.source_class for entry in entries})


def persistence(entries: list[schemas.ClusterEntry]) -> int:
    """Count distinct weeks a cluster has received entries.

    :param entries: The cluster's log entries.
    :returns: The number of distinct weeks.
    """
    return len({entry.week for entry in entries})


def entries_through(entries: list[schemas.ClusterEntry], week: str) -> list[schemas.ClusterEntry]:
    """Scope a cluster's entries to those recorded up to and including a week.

    Week labels sort lexically (``"2026-W24" <= "2026-W25"``), so scoping is a
    plain string comparison — no calendar arithmetic, and it re-runs
    identically regardless of what gets logged in later weeks.

    :param entries: The cluster's log entries.
    :param week: The boundary week label.
    :returns: Entries whose week is less than or equal to ``week``.
    """
    return [entry for entry in entries if entry.week <= week]


def has_primary_source(entries: list[schemas.ClusterEntry], catalog: schemas.SourceCatalog) -> bool:
    """Check a cluster has at least one entry from a source that makes the news.

    :param entries: The cluster's log entries.
    :param catalog: The parsed source catalog, which marks the primary classes.
    :returns: ``True`` when some entry comes from a primary class.
    """
    return any(catalog.is_primary(entry.source_class) for entry in entries)


def strongest(entries: list[schemas.ClusterEntry]) -> schemas.ClusterEntry:
    """Pick a cluster's strongest entry: most significant first, most recent breaks ties.

    :param entries: The cluster's log entries.
    :returns: The strongest entry.
    """
    return min(entries, key=lambda entry: (-(entry.significance or 3), -entry.date.toordinal()))


def momentum(entries: list[schemas.ClusterEntry], week: str) -> tuple[int, float]:
    """Compare entries this week against the cluster's prior rate.

    :param entries: The cluster's log entries.
    :param week: The current week label.
    :returns: ``(this_week_count, prior_weeks_average)``.
    """
    prior = [e for e in entries if e.week != week]
    prior_weeks = {e.week for e in prior}
    prior_rate = len(prior) / len(prior_weeks) if prior_weeks else 0.0
    return len([e for e in entries if e.week == week]), prior_rate


def spread(entries: list[schemas.ClusterEntry]) -> int:
    """Count distinct regions — a secondary convergence signal.

    :param entries: The cluster's log entries.
    :returns: The number of distinct regions.
    """
    return len({entry.region for entry in entries})


def is_candidate_trend(entries: list[schemas.ClusterEntry], catalog: schemas.SourceCatalog) -> bool:
    """Check the documented candidate-trend threshold.

    :param entries: The cluster's log entries.
    :param catalog: The parsed source catalog, for the primary-source rule.
    :returns: ``True`` when the cluster crosses the threshold.
    """
    return (
        len(entries) >= CANDIDATE_TREND_MIN_FINDINGS
        and reach(entries) >= CANDIDATE_TREND_MIN_CLASSES
        and persistence(entries) >= CANDIDATE_TREND_MIN_WEEKS
        and has_primary_source(entries, catalog)
    )


def trend_status(entries: list[schemas.ClusterEntry], catalog: schemas.SourceCatalog) -> str:
    """Derive a cluster's status label: strengthening, candidate-trend, or emerging.

    Below the threshold a cluster is *emerging*; once well past it (broad
    reach, sustained six-plus weeks) it is *strengthening*.
    Labels are derived each run; nothing about them is stored.

    :param entries: The cluster's log entries.
    :param catalog: The parsed source catalog, for the primary-source rule.
    :returns: One of ``"strengthening"``, ``"candidate-trend"``, ``"emerging"``.
    """
    if not is_candidate_trend(entries, catalog):
        return "emerging"

    if persistence(entries) >= 6 and reach(entries) >= 4:
        return "strengthening"

    return "candidate-trend"


def tally_text(entries: list[schemas.ClusterEntry]) -> str:
    """Render a human-readable cluster tally.

    :param entries: The cluster's log entries.
    :returns: e.g. ``"2 findings · 3 source classes · 4 weeks"`` (singular forms when 1, "first week" for one week).
    """
    weeks = persistence(entries)
    weeks_text = "first week" if weeks == 1 else f"{weeks} weeks"
    return (
        f"{len(entries)} finding{'s' if len(entries) != 1 else ''} · "
        f"{reach(entries)} source class{'es' if reach(entries) != 1 else ''} · "
        f"{weeks_text}"
    )


def sort_ranked(
    clusters: list[tuple[Cluster, list[schemas.ClusterEntry]]],
    catalog: schemas.SourceCatalog,
) -> list[tuple[Cluster, list[schemas.ClusterEntry]]]:
    """Rank clusters by importance, strongest first (derived, never stored).

    Rule of thumb: primary sources first, then reach x persistence. A
    presentation aid, not a gate; the datapoint tie-breaker stays qualitative
    and is left to the digest prose.

    :param clusters: ``(cluster, entries)`` pairs to rank.
    :param catalog: The parsed source catalog, for the primary-source rule.
    :returns: The pairs, strongest first.
    """

    def sort_key(pair: tuple[Cluster, list[schemas.ClusterEntry]]) -> tuple[int, int]:
        _, entries = pair
        return (
            0 if has_primary_source(entries, catalog) else 1,
            -(reach(entries) * persistence(entries)),
        )

    return sorted(clusters, key=sort_key)


def sort_lead_candidates(
    candidates: list[tuple[Cluster, list[schemas.ClusterEntry], list[schemas.ClusterEntry]]],
    week: str,
    catalog: schemas.SourceCatalog,
) -> list[tuple[Cluster, list[schemas.ClusterEntry], list[schemas.ClusterEntry]]]:
    """Rank the week's candidate stories, strongest first.

    A different question from ``sort_ranked``'s standing evidence weight: the
    Vision wants what is emerging, not what is already big. So the lead is
    the cluster with the most novelty (a new story, or one reaching new source
    classes and regions), then the most source classes among this week's
    entries, then burst size, candidate-trend status and momentum against the
    cluster's prior rate. The gate's significance does not rank stories: the
    small model scores frontier-lab news higher, and ranking on it doubled
    that news's share of the digest.

    :param candidates: ``(cluster, scoped_entries, this_week_entries)`` triples;
        ``scoped_entries`` is the cluster's entries through this week.
    :param week: The current week label.
    :param catalog: The parsed source catalog, for the primary-source rule.
    :returns: The triples, strongest lead first.
    """

    def sort_key(
        item: tuple[Cluster, list[schemas.ClusterEntry], list[schemas.ClusterEntry]],
    ) -> tuple[int, int, int, int, float]:
        _, scoped, this_week = item
        this_week_count, prior_rate = momentum(scoped, week)
        return (
            -novelty(scoped, week),
            -reach(this_week),
            -len(this_week),
            0 if is_candidate_trend(scoped, catalog) else 1,
            -this_week_count / max(prior_rate, 1),
        )

    return sorted(candidates, key=sort_key)


def novelty(entries: list[schemas.ClusterEntry], week: str) -> int:
    """Score how new a cluster's story is this week (derived, never stored).

    A cluster seen for the first time scores 1; an established one scores one
    point per source class and per region it reaches for the first time —
    a story spreading beyond its first outlets is how emergence shows.

    :param entries: The cluster's entries through ``week``.
    :param week: The current week label.
    :returns: The novelty score, 0 for a story moving only where it already was.
    """
    earlier = [e for e in entries if e.week < week]
    current = [e for e in entries if e.week == week]
    if not earlier:
        return 1
    new_classes = {e.source_class for e in current} - {e.source_class for e in earlier}
    new_regions = {e.region for e in current} - {e.region for e in earlier}
    return len(new_classes) + len(new_regions)


def group_key_by_theme(findings: list[Finding]) -> dict[str, list[Finding]]:
    """Group findings by the themes the harvest's judgement call assigned them.

    A theme is a tag on the finding, not a bucket owned by its source: one
    finding can carry several themes (or none — those end up unmatched, noted
    in the run summary), and a finding joins clusters in every theme it tags.

    :param findings: The week's findings.
    :returns: Theme id to findings map.
    """
    grouped: dict[str, list[Finding]] = {}

    for finding in findings:
        for theme in finding.theme_ids:
            grouped.setdefault(theme, []).append(finding)

    return grouped
