# Tasks

## 1. Week definition

- [x] 1.1 `cadence.py` on ISO weeks: window Monday–Sunday, label from the ISO week, `last_closed_window` the week before today's, `weeks_before`; tests "Monday run", "Friday run", "Saturday run", a year boundary (2026-W53 / 2027-W01); verify `./run pytest tests/agents/vision_watch/test_cadence.py` passes
- [x] 1.2 CLI: default week, `--on` for any day of the week, drop the non-Friday warning, refuse an open week; tests "Backfilling a past week", "Week still open", "Non-Friday simulation"
- [x] 1.3 Sweep date bounds, `snapshot-feeds` open week, feed truncation check against the week's Monday; tests "Old feed entries", "Busy feed with a snapshot", "Backfilled week"
- [x] 1.4 `month_weeks` by the week's Thursday; tests "July 2026" (W27–W31), "Week across two months" (W40 in October) and the existing September regression (W36–W39)
- [x] 1.5 README (week, Monday run order, cron example) and the `openspec/config.yaml` glossary ("week"); full suite and ruff clean
- [x] 1.6 `monthly-digest` without `--month` targets the latest complete month (skipped when already composed); an explicit month not complete is refused; README crontab runs it every Monday after the weekly; tests "Monday run without a month", "Month already composed", "Month not complete", "Monthly without a month"

## 2. Newsletter arrival

- [x] 2.1 `received` on newsletter candidates (attributed and `inbox`), window gate with the 7-day arrival grace; tests "Newsletter reports last week's news", "Newsletter item older than a week", and a feed item dated before the week still rejected
- [x] 2.2 Previous-week anchors in the near-match fold, late items only, detail "already in <week> as <finding id>"; test "Late item already in last week's digest" and that an in-week follow-up is not folded
- [x] 2.3 `replay-gate` needs no anchors: it re-judges only relevance rejects (`off_theme`, `source_cap`), and late items were rejected `out_of_window`, so they never reach it; estimator unchanged; verify the harvest and replay tests pass

## 3. Migration

- [x] 3.1 Migration script outside the package (`~/.cache/vw/migrate_monday_weeks.py`), dry run on a scratch copy of the live workspace: findings moved per week, dropped (before 22 June), candidates to re-gate, token estimate; review with the user before spending
- [x] 3.2 Archive the live `evidence/`, `clusters/`, `digests/`; run the migration for W26–W38 and `simulate-harvest --on 2026-09-27` for W39; report late items folded into the previous week
- [x] 3.3 Rebuild clusters W26–W39, recompose the 14 weeklies and the July and August monthlies (September is left to the first Monday run, 5 October, by the operator's choice); check labels, counts, links (no trackers), and report token usage; W39 was topped up with 7 arXiv categories refused on the first harvest and 37 recorded findings its feeds had rolled past
