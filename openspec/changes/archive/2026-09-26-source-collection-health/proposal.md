# Proposal

## Why

Collection was blind in ways nobody noticed. The arXiv RSS feeds are empty at weekends (every harvest so far), so preprints never arrived. Empty feeds counted as quiet sources. Busy feeds lost the start of the week. Listing pages yielded stale headline items. And source failures surfaced only in the run log: 28 of 102 sources produced nothing in the live weeks.

## Changes

- arXiv categories read through the arXiv API for the exact window, without scraping.
- Every feed entry is considered; an empty or unreachable feed falls back to scraping the page, flagged.
- A feed whose history no longer reaches the window start is flagged as truncated; a daily `snapshot-feeds` command keeps the open week's entries, merged at harvest.
- Listing extraction takes the newest dated items, up to 10.
- Each harvest writes a per-source report; a source-health step labels each source and emails the dev list, opt-in, when the set of unhealthy sources changes.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/source-collection`: arXiv channel, feed fallbacks and flags, snapshots, newest-item extraction, source health.
- `vision-watch/runs`: `snapshot-feeds` command; `--send` on harvests sends the health alert.
