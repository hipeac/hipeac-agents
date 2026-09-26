"""Harvest node: collects, verifies, and records the week's developments.

Layout — the reviewable unit per judgement call is the
(prompt, model, node-logic) triple, so the node is a package:

- ``prompts.py`` — the five LLM prompt constants.
- ``models.py`` — the five structured-output models, one per prompt.
- ``context.py`` — ``HarvestContext``, the LLM runner wrappers.
- ``gates.py`` — judgement-free gates and helpers (unit-tested with no mocking).
- ``channels.py`` — collection channels, one function per channel.
- ``node.py`` — orchestration: channels, near-match fold, re-sample, writes.

LLM-JUDGEMENT CALLS — review before the first live run:

1. ``CandidateList`` / ``CANDIDATE_EXTRACTION`` — extracting candidate items
   from a scraped page or newsletter body.
2. ``GateVerdict`` / ``GATE`` — merged verification gate: themes, tier, title.
5. ``NearMatchGroups`` / ``NEAR_MATCH`` — same event under a different URL
   is one finding, not two.

Boundaries: collect, verify, and record only — no grouping, no convergence
judgement, no composing.
"""

from .gates import (  # noqa: F401
    build_due_list,
    cap_tier,
    dedupe_rejects,
    duplicate_gate,
    extract_links,
    find_id,
    headline_in_body,
    kept_findings,
    parse_iso_date,
    pick_resample,
    window_gate,
)
from .models import (  # noqa: F401
    CandidateItem,
    CandidateList,
    GateVerdict,
    NearMatchGroups,
)
from .node import harvest_node  # noqa: F401


__all__ = [
    "CandidateItem",
    "CandidateList",
    "NearMatchGroups",
    "GateVerdict",
    "build_due_list",
    "cap_tier",
    "dedupe_rejects",
    "duplicate_gate",
    "extract_links",
    "find_id",
    "harvest_node",
    "headline_in_body",
    "kept_findings",
    "parse_iso_date",
    "pick_resample",
    "window_gate",
]
