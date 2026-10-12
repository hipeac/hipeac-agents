## Why

`weekly-digest` composes and mails a week even when that week was never harvested: with no evidence it writes a "Quiet week" digest and sends it to the board. On 2026-10-05 this happened after the digest was run without `weekly-harvest`; the digest is write-once and sent at most once, so the mistake could not be undone by re-running.

## What Changes

- `weekly-digest` refuses to compose or send a week that has no harvest record, exits non-zero and says to run `weekly-harvest` first.
- A week that already has a recorded digest is not gated, so a digest composed and reviewed earlier can still be sent with `--send`.
- `--intro-only` is not gated either, since it only rewrites a recorded digest.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `vision-watch/runs`: adds the harvest precondition to `weekly-digest`.

## Impact

- `hipeac_agents/cli.py`: precondition check before the graph runs, before any LLM call or send.
- `hipeac_agents/agents/vision_watch/workspace.py`: a small read helper for the harvest record.
- Tests in `tests/test_cli.py`; README note under the weekly digest section.
- Weeks harvested before the marker existed need a one-off backfill of the marker (see design).
