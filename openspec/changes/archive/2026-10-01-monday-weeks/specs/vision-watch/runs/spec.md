## MODIFIED Requirements

### Requirement: Commands

The system SHALL offer these commands: `weekly-harvest` (collect the week's evidence, then check source health), `weekly-digest` (cluster the week's findings and compose the weekly digest), `monthly-digest` (synthesise a calendar month, the latest complete one by default), `simulate-harvest` (a harvest for an explicit past date), `snapshot-feeds` (capture the open week's feed entries, meant to run daily) and `replay-gate` (re-judge recorded weeks). Any other command SHALL be rejected with a usage error.

#### Scenario: Unknown command

- **WHEN** the operator runs a command that is not one of these
- **THEN** the run exits with a usage error and does nothing

#### Scenario: Monthly without a month

- **WHEN** the operator runs `monthly-digest` without `--month YYYY-MM`
- **THEN** the run targets the latest complete month

#### Scenario: Simulated harvest without a date

- **WHEN** the operator runs `simulate-harvest` without `--on YYYY-MM-DD`
- **THEN** the run exits with a usage error naming the missing flag

### Requirement: Editorial week

The editorial week SHALL run Monday through Sunday. A week SHALL be labelled `YYYY-Www` after its ISO week. When no date is given, a harvest or weekly digest SHALL target the most recently closed week: the week that ended on the previous Sunday. A week whose Sunday lies in the future SHALL never be targeted by default. The weekly harvest and digest are meant to run on Monday early morning.

#### Scenario: Monday run

- **WHEN** a harvest runs on Monday 5 October 2026 without `--on`
- **THEN** it targets Monday 28 September – Sunday 4 October, labelled `2026-W40`

#### Scenario: Friday run

- **WHEN** a harvest runs on Friday 2 October 2026 without `--on`
- **THEN** it targets the week that closed on Sunday 27 September, `2026-W39`, not the week still open

#### Scenario: Saturday run

- **WHEN** a harvest runs on Saturday 3 October 2026 without `--on`
- **THEN** it still targets `2026-W39`: W40 closes only on Sunday 4 October

### Requirement: Running as of a date

Harvests and `weekly-digest` SHALL accept `--on YYYY-MM-DD` and target the week containing that date; `simulate-harvest` requires it. A run SHALL refuse a week that has not closed yet.

#### Scenario: Backfilling a past week

- **WHEN** the operator runs `simulate-harvest --on 2026-06-24`
- **THEN** the harvest targets Monday 22 – Sunday 28 June 2026, labelled `2026-W26`

#### Scenario: Week still open

- **WHEN** the operator runs `weekly-digest --on` with a date whose week closes in the future
- **THEN** the run refuses with exit code 2 and does nothing

#### Scenario: Non-Friday simulation

- **WHEN** the operator runs `simulate-harvest --on` with a Wednesday
- **THEN** the harvest targets the Monday–Sunday week containing it, without a warning
