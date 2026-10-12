# Proposal

## Why

The per-source cap (at most 4 findings per source per week) throws away evidence that has already been judged. Over W26–W39 it rejected 447 verified findings, against 556 kept. It saves no model cost: the verdicts are paid before it runs, and cost is already bounded by the pre-verdict pick of 8 per source.

It also treats the inbox and the sweep as single sources, although each gathers many. In W39 this cut OpenAI's unfiled EU AI Act incident report.

Digest size doesn't depend on the pool: at most 4 candidate stories per theme and 4 findings per story. So more findings mean stories backed by more links, not a longer digest.

The skew the cap once guarded against is now handled by the ai-news class cap, and by story ranking without significance.

## What Changes

- The per-source cap is removed. A source keeps every finding that passes the verdict. Its volume stays bounded by the pre-verdict pick of 8.
- The class cap stays (ai-news: 6 a week) and now applies directly to the verified findings.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/source-collection`: Per-source volume cap removed; Class volume cap no longer runs after it.

## Impact

- **Code:** `nodes/harvest/node.py` (`cap_volume`, `_cap_source_volume` and its constants) and its tests. `replay.py` keeps calling `cap_volume`.
- **Workspace:** weekly pools grow. By the W26–W39 record, up to +80% before the class cap; much less after it, since 190 of the 447 were ai-news. The weekly clustering call grows with the pool (base model, one call a week). Signals logs grow.
- **Past weeks:** they change only through `replay-gate`, which re-judges `source_cap` rejects.
