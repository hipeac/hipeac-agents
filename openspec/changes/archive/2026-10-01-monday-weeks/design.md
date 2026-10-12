# Design

## Context

`cadence.py` defines the Saturday–Friday window (`current_window`, `last_closed_window`, `weekly_label` from the closing Friday, `weeks_before`); the CLI, `snapshot-feeds`, the sweep's date bounds and `month_weeks` build on it. The window gate (`_pre_gate`) compares a candidate's own date with the window; newsletter candidates take the message's date only when they have none (`_dated_by_message`). The duplicate gate matches canonical URLs against every recorded finding; the near-match fold (`_fold_near_matches`, one LLM call per 50 titles) runs within the week only. W26–W39 exist as evidence, clusters, weeklies, ledgers and three monthlies, none sent. Rejected items carry no date, except near-window rejects (publish date in the detail).

## Goals / Non-Goals

**Goals:**
- One week definition everywhere: Monday–Sunday, the ISO week.
- A newsletter item counts in the week its newsletter arrived, unless it already counted.
- W26–W39 on the new windows, with the digests the board would have received.

**Non-Goals:**
- A scheduler. The operator (or cron/launchd) runs `weekly-harvest` then `weekly-digest` on Monday morning, as today.
- A grace for feeds or pages. Their items are dated by the source and the previous week's harvest saw them.
- Re-judging the recorded findings: their verdicts came from the current gate on 2026-09-28.

## Decisions

### ISO week as the week

A Mon–Sun window is exactly the ISO week, so the label no longer needs a "closing day" rule: `week_of(day)` is the day's ISO week, and the window is its Monday–Sunday. `last_closed_window(today)` is the ISO week before today's. Alternative: keep Sat–Fri and only move the run to Saturday. Rejected: the board asked for Monday–Sunday, and the labels would still disagree with the ISO calendar by two days.

### Arrival date on the candidate

A newsletter candidate carries the message's date as `received` (a new, optional `CandidateItem` field, never persisted). The window gate passes a candidate when its date is in the week, or when it has `received` in the week and its date is at most 7 days before `received`. The 7 days cover a weekly newsletter's lag; the audit still records items older than that as `out_of_window` with their days outside. Board tips keep their current rule (no date check).

### Checking against the previous week

A late item (dated before the week) goes through the existing checks: the URL duplicate gate against every recorded finding, then, after verdicts, the near-match fold with the previous week's findings added as anchors. An anchor is never dropped or merged into; a group holding an anchor and late items rejects the late items as `duplicate` with detail "already in <week> as <finding id>". Items dated inside the week do not fold into last week's findings: a follow-up story is new evidence, and clustering links it. Cost: none in a week without late items; otherwise one near-match call per 40 or so of last week's findings, 1–3 small-model calls.

Alternative: compare titles with string similarity in code. Rejected: on W26–W39 it found 2 of the 95 late items, where different outlets word the same event differently; the near-match prompt already exists for this.

### Month: the month holding most of the week's days

A week belongs to the month of its Thursday. No week is split between two monthlies, a straddling week goes where four or more of its days are, and it is the rule ISO uses for years, so `2026-W53` belongs to 2026 in both. For 2026 it keeps July W27–W31, August W32–W35 and September W36–W39, as today. The monthly is composed on the Monday its last week closes, after that week's digest. Alternatives: the closing Sunday (moves W31 to August, and a week of 1 August sits in August on one day) and calendar days (splits a week between two monthlies, so one story shows in both).

### Migration from recorded evidence (W26–W38), fresh harvest (W39)

Feeds have moved on, so past weeks cannot be collected again; every candidate the harvests saw is on disk. A one-off migration script (kept outside the package, like the link repair) builds the new weeks:

1. Findings move to the ISO week of their date and are renumbered. Findings dated before 22 June (old W26's Saturday–Sunday) fall outside W26–W39 and stay only in the archive.
2. Rejects stay under their old label (the audit has no dates, except near-window rejects).
3. Near-window rejects whose publish date now falls inside a week, and late newsletter rejects (published at most 7 days before their old week, assigned to the new week with the same label, whose Monday–Friday it shares), are gated again in that week: duplicate gate, triage, pick, verdict on cached pages or their own titles (as `replay` does), then the previous-week fold.
4. W39 (21–27 September) is harvested fresh with `simulate-harvest --on 2026-09-27`, since the recorded harvest stopped on Friday 25 and feeds still hold that week. The migrated W26–W38 findings are its duplicate baseline.
5. Clusters are rebuilt from scratch, week by week; then the 14 weeklies and the July–September monthlies are recomposed.

Alternative: shift labels without re-bucketing (old W39 → new W39). Rejected: Saturday–Sunday items would sit in the wrong week, and the window rule would not hold for past weeks.

## Risks / Trade-offs

- [Arrival assignment in the migration is approximate: a late newsletter reject's message date is not on disk] → It goes to the new week with the same label, which shares five of the old week's seven days; the previous-week fold catches doubles.
- [The fresh W39 harvest sees the 15 sources added on 2026-09-30, the migrated weeks do not] → Noted in the W39 run summary; it is the first week of the new catalog.
- [Newsletters with a weekly recap may repeat items the week before already had] → URL duplicate gate plus the previous-week fold; measured on the migrated weeks (late items folded) and reported.
- [A digest run before the harvest on Monday composes an empty week] → The README orders the two commands; the digest already reports a quiet week rather than failing.

## Migration Plan

1. Land the code (cadence, CLI, window gate, fold, `month_weeks`, snapshots) with tests.
2. Dry run of the migration: count moved findings, candidates to re-gate and estimated tokens; review before spending.
3. Archive `evidence/`, `clusters/`, `digests/` to `_archive/vision-watch-before-monday-weeks-<date>.tar.gz`.
4. Migrate W26–W38, harvest W39, rebuild clusters, recompose weeklies and monthlies.
5. From Monday 5 October: `weekly-harvest` then `weekly-digest` each Monday early morning (W40 first).

Rollback: restore the archive and the previous code.
