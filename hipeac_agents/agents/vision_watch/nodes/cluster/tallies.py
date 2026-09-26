"""Judgement-free cluster tallies and the candidate-trend threshold.

Every function here is deterministic Python — unit-tested with no mocking,
no LLM. Everything the digest needs about a cluster is tallied from its log
entries at read time and never stored.
"""

from hipeac_agents.agents.vision_watch import schemas
from hipeac_agents.agents.vision_watch.schemas import Cluster, Finding


# Candidate-trend threshold: at least 4 findings across at least 3 source
# classes over at least 3 distinct weeks, including at least one tier-1 or
# tier-2 finding.
CANDIDATE_TREND_MIN_FINDINGS = 4
CANDIDATE_TREND_MIN_CLASSES = 3
CANDIDATE_TREND_MIN_WEEKS = 3


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


def evidence_strength(entries: list[schemas.ClusterEntry]) -> int:
    """Return the best (lowest-number) tier present in a cluster.

    :param entries: The cluster's log entries.
    :returns: The lowest tier, 1-4.
    """
    return min(entry.tier for entry in entries)


def strongest(entries: list[schemas.ClusterEntry]) -> schemas.ClusterEntry:
    """Pick a cluster's strongest entry: best tier first, most recent breaks ties.

    :param entries: The cluster's log entries.
    :returns: The strongest entry.
    """
    return min(entries, key=lambda entry: (entry.tier, -entry.date.toordinal()))


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


def independence_share(entries: list[schemas.ClusterEntry], catalog: schemas.SourceCatalog) -> float:
    """Compute the share of a cluster's entries leaning on low-independence sources.

    Europe agreeing with itself is real but weaker than the world independently
    converging; a candidate trend resting only on low-independence (e.g.
    ``eu-uptake``) sources is framed as European uptake, not momentum.

    :param entries: The cluster's log entries.
    :param catalog: The parsed source catalog.
    :returns: The share (0.0-1.0) of entries from low-independence sources.
    """
    independence = {s.id: s.independence for s in catalog.sources}

    if not entries:
        return 0.0

    low = sum(1 for e in entries if independence.get(e.source_id) == "low")

    return low / len(entries)


def is_candidate_trend(entries: list[schemas.ClusterEntry]) -> bool:
    """Check the documented candidate-trend threshold.

    :param entries: The cluster's log entries.
    :returns: ``True`` when the cluster crosses the threshold.
    """
    return (
        len(entries) >= CANDIDATE_TREND_MIN_FINDINGS
        and reach(entries) >= CANDIDATE_TREND_MIN_CLASSES
        and persistence(entries) >= CANDIDATE_TREND_MIN_WEEKS
        and evidence_strength(entries) <= 2
    )


def threshold_progress(entries: list[schemas.ClusterEntry]) -> str:
    """Render a cluster's progress toward the candidate-trend threshold.

    Makes the promotion ladder visible: the board sees exactly which of the
    four criteria (4 findings, 3 source classes, 3 weeks, tier ≤ 2) a
    cluster already meets and which it needs.

    :param entries: The cluster's log entries.
    :returns: Text like ``"3/4 findings · 1/3 source classes · 2/3 weeks — needs one more source class"``.
    """
    findings = len(entries)
    classes = reach(entries)
    weeks = persistence(entries)
    met = (
        findings >= CANDIDATE_TREND_MIN_FINDINGS,
        classes >= CANDIDATE_TREND_MIN_CLASSES,
        weeks >= CANDIDATE_TREND_MIN_WEEKS,
        evidence_strength(entries) <= 2,
    )
    missing = []

    if not met[0]:
        missing.append(f"{CANDIDATE_TREND_MIN_FINDINGS - findings} more findings")
    if not met[1]:
        missing.append(f"{CANDIDATE_TREND_MIN_CLASSES - classes} more source classes")
    if not met[2]:
        missing.append(f"{CANDIDATE_TREND_MIN_WEEKS - weeks} more weeks")

    progress = (
        f"{findings}/{CANDIDATE_TREND_MIN_FINDINGS} findings · "
        f"{classes}/{CANDIDATE_TREND_MIN_CLASSES} source classes · {weeks}/{CANDIDATE_TREND_MIN_WEEKS} weeks"
    )

    if not met[3]:
        missing.append("a tier-1 or tier-2 finding")

    needs = " — needs " + " and ".join(missing) if missing else " — threshold met"
    return progress + needs


def trend_status(entries: list[schemas.ClusterEntry]) -> str:
    """Derive a cluster's status label: strengthening, candidate-trend, or emerging.

    Below the threshold a cluster is *emerging*; once well past it (broad
    reach, sustained six-plus weeks, a tier-1 anchor) it is *strengthening*.
    Labels are derived each run; nothing about them is stored.

    :param entries: The cluster's log entries.
    :returns: One of ``"strengthening"``, ``"candidate-trend"``, ``"emerging"``.
    """
    if not is_candidate_trend(entries):
        return "emerging"

    if persistence(entries) >= 6 and reach(entries) >= 4 and evidence_strength(entries) == 1:
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

    Rule of thumb: tier first, then reach x persistence, discounted for low
    independence. A presentation aid, not a gate; the datapoint tie-breaker
    stays qualitative and is left to the digest prose.

    :param clusters: ``(cluster, entries)`` pairs to rank.
    :param catalog: The parsed source catalog, for the independence discount.
    :returns: The pairs, strongest first.
    """

    def sort_key(pair: tuple[Cluster, list[schemas.ClusterEntry]]) -> tuple[int, int, float]:
        _, entries = pair
        return (
            0 if evidence_strength(entries) <= 2 else 1,
            -(reach(entries) * persistence(entries)),
            independence_share(entries, catalog),
        )

    return sorted(clusters, key=sort_key)


def sort_lead_candidates(
    candidates: list[tuple[Cluster, list[schemas.ClusterEntry], list[schemas.ClusterEntry]]],
    week: str,
    catalog: schemas.SourceCatalog,
) -> list[tuple[Cluster, list[schemas.ClusterEntry], list[schemas.ClusterEntry]]]:
    """Rank clusters for the week's lead story ("One big thing"), strongest first.

    A different question from ``sort_ranked``'s standing evidence weight: the
    Vision wants what is emerging, not what is already big. So the lead is
    the cluster with the most forward-significant entry this week, then the
    most novelty (a new story, or one reaching new source classes and
    regions), then best tier this week, burst size, candidate-trend status,
    momentum against the cluster's prior rate, and an independence discount.

    :param candidates: ``(cluster, scoped_entries, this_week_entries)`` triples;
        ``scoped_entries`` is the cluster's entries through this week.
    :param week: The current week label.
    :param catalog: The parsed source catalog, for the independence discount.
    :returns: The triples, strongest lead first.
    """

    def sort_key(
        item: tuple[Cluster, list[schemas.ClusterEntry], list[schemas.ClusterEntry]],
    ) -> tuple[int, int, int, int, int, float, float]:
        _, scoped, this_week = item
        this_week_count, prior_rate = momentum(scoped, week)
        return (
            -max(entry.significance or 3 for entry in this_week),
            -novelty(scoped, week),
            evidence_strength(this_week),
            -len(this_week),
            0 if is_candidate_trend(scoped) else 1,
            -this_week_count / max(prior_rate, 1),
            independence_share(scoped, catalog),
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
