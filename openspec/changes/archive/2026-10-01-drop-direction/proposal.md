# Proposal

## Why

Every verdict asks the small model for a `direction` (strengthens, weakens or new relative to the trend the Vision describes), added on 2026-09-26 as a first take on "which way does this push". Nothing reads it: clustering, the weekly digest and the monthly digest ignore it, and the weekly items' lean (per open question, written by the thinking model) and the "new topic" tag replaced it. Over W26–W39 it was 664 strengthens, 54 weakens, 1 new, so it carries no information. It costs output tokens on hundreds of verdicts a week.

## What Changes

- The verdict no longer asks for or returns a direction.
- Findings and cluster entries no longer carry one. Files written before still load; the field is ignored on read and dropped when a file is rewritten.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/candidate-verification`: Judgement verdict without a direction.

## Impact

- **Code:** `nodes/harvest/models.py` (verdict field and `Direction` import), `nodes/harvest/prompts.py` (the "DIRECTION and HORIZON" step keeps horizon only), `nodes/harvest/channels.py` (`_judged`), `schemas.py` (`Direction`, `Finding.direction`, `ClusterEntry.direction`), `nodes/cluster/node.py`, tests that set it.
- **Workspace:** none; old `direction` values stay in recorded files until they are rewritten (the monday-weeks migration rewrites all of W26–W39).
