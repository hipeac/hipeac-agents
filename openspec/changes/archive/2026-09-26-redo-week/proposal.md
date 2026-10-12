# Proposal

## Why

Redoing a week meant deleting files by hand. Finding ids are reused when a week is harvested again, so stale cluster entries silently pointed at different findings (the W39 digest was composed on nine of them).

## Changes

- `--redo` on `weekly-harvest`, `simulate-harvest` and `weekly-digest` backs the week up and clears its cluster entries before running.
- A harvest refuses to run while the week still has cluster entries from an earlier harvest.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/runs`: adds the redo flag.
- `vision-watch/clustering`: the stale-entry rule is now enforced.
