"""Cluster node: groups the week's findings into per-theme clusters.

Layout:

- ``prompts.py`` — the one LLM prompt constant.
- ``models.py`` — the structured-output model, paired with the prompt.
- ``tallies.py`` — judgement-free tallies, the candidate-trend threshold, and
  the ranking rule (unit-tested with no mocking).
- ``node.py`` — orchestration: grouping call, log appends, per-theme report.

LLM-JUDGEMENT CALL — review before the first live run:

- ``GroupingPlan`` / ``GROUPING_BAR`` — which cluster each finding extends.

Boundaries: groups and tallies only; makes no claims and writes no digest.
Appends to cluster logs only, never edits earlier entries.
"""

from .models import (  # noqa: F401
    GroupingDecision,
    GroupingPlan,
    NewCluster,
)
from .node import cluster_node  # noqa: F401
from .tallies import (  # noqa: F401
    CANDIDATE_TREND_MIN_CLASSES,
    CANDIDATE_TREND_MIN_FINDINGS,
    CANDIDATE_TREND_MIN_WEEKS,
    entries_through,
    group_key_by_theme,
    has_primary_source,
    independence_share,
    is_candidate_trend,
    momentum,
    novelty,
    persistence,
    reach,
    sort_lead_candidates,
    sort_ranked,
    spread,
    strongest,
    tally_text,
    trend_status,
)


__all__ = [
    "CANDIDATE_TREND_MIN_CLASSES",
    "CANDIDATE_TREND_MIN_FINDINGS",
    "CANDIDATE_TREND_MIN_WEEKS",
    "GroupingDecision",
    "GroupingPlan",
    "NewCluster",
    "cluster_node",
    "entries_through",
    "group_key_by_theme",
    "has_primary_source",
    "independence_share",
    "is_candidate_trend",
    "momentum",
    "persistence",
    "reach",
    "novelty",
    "sort_lead_candidates",
    "sort_ranked",
    "spread",
    "strongest",
    "tally_text",
    "trend_status",
]
