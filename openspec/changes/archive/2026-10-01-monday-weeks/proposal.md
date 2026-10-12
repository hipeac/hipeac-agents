# Proposal

## Why

The window check uses an item's publish date, not the day it reached us. Newsletters report news a few days late, so an item published just before the week starts is rejected, and the week before never saw it: over W26–W39, 95 newsletter items were lost this way, 93 of them never recorded in any week (2 had been covered by another outlet). Separately, a Friday-evening run misses what arrives later that Friday. The board also asked for weeks that read plainly: Monday to Sunday, with the digest on Monday morning.

## What Changes

- **BREAKING** The editorial week runs Monday through Sunday, labelled by its ISO week (a Mon–Sun week is exactly an ISO week). Harvest and weekly digest run on Monday early morning for the week that closed on Sunday. Weeks W26–W39 are re-labelled on the new windows; their evidence, clusters, weekly digests, ledgers and the July–September monthly digests are rebuilt.
- A month covers the weeks with most of their days in it (the week's Thursday decides, as ISO does for years). July–September 2026 keep their weeks: July W27–W31, August W32–W35, September W36–W39.
- Newsletter items count by arrival: an item from a newsletter received in the week passes the window check when it was published at most 7 days before the email. Such a late item is rejected `duplicate` when it is already recorded in an earlier week (same URL) or reports the same event as one of the previous week's findings (near-match), so nothing is reported twice.
- The "not a Friday" warning on `simulate-harvest --on` is dropped: any date in the week names the week.
- `monthly-digest` without `--month` targets the latest complete month and skips a month already composed, so it runs every Monday after the weekly; an explicit month that is not complete is refused.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/runs`: Editorial week (Monday–Sunday, ISO week label, Monday run); Running as of a date (no weekday warning).
- `vision-watch/source-collection`: Feed channel and General sweep bounded by Monday–Sunday; arXiv channel's weekend scenario becomes a Monday run.
- `vision-watch/candidate-verification`: Gate order steps 1–2 (arrival grace for newsletter items, duplicate check against the previous week); One development, one finding (late items fold into the previous week's findings).
- `vision-watch/monthly-digest`: Weeks in a month (most of the week's days).

## Impact

- **Code:** `cadence.py` (windows, labels, last closed week), `cli.py` (default week, `--on`, warning), `nodes/harvest/` (candidate arrival date from the message, window gate, previous-week near-match), `nodes/monthly/node.py` (`month_weeks`), `snapshot-feeds` window, their tests; README and the `openspec/config.yaml` glossary ("week").
- **Workspace migration:** W26–W38 rebuilt from the recorded candidates without collecting again; W39 (21–27 September) harvested fresh, since the recorded harvest stopped on Friday 25. Clusters rebuilt from scratch, 14 weeklies and 3 monthlies recomposed. Estimated cost: about 150k base-model tokens for clustering, 110k thinking-model tokens for the weeklies and 20k for the monthlies, one harvest's worth for W39, and small-model calls for the candidates newly inside a week (measured by a dry run before spending). Nothing has been sent to the board, so no sent digest changes.
- **Operations:** the weekly job moves to Monday early morning (`weekly-harvest`, then `weekly-digest`); `snapshot-feeds` stays daily. The first live week is W40 (28 September – 4 October), run on Monday 5 October.
