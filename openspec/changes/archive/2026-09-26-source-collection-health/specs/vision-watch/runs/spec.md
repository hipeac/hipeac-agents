## MODIFIED Requirements

### Requirement: Commands

The system SHALL offer these commands: `weekly-harvest` (collect the week's evidence, then check source health), `weekly-digest` (cluster the week's findings and compose the weekly digest), `monthly-digest` (synthesise a calendar month), `simulate-harvest` (a harvest for an explicit past date), `snapshot-feeds` (capture the open week's feed entries, meant to run daily) and `replay-gate` (re-judge recorded weeks). Any other command SHALL be rejected with a usage error.

#### Scenario: Unknown command

- **WHEN** the operator runs a command that is not one of these
- **THEN** the run exits with a usage error and does nothing

#### Scenario: Monthly without a month

- **WHEN** the operator runs `monthly-digest` without `--month YYYY-MM`
- **THEN** the run exits with a usage error naming the missing flag

#### Scenario: Simulated harvest without a date

- **WHEN** the operator runs `simulate-harvest` without `--on YYYY-MM-DD`
- **THEN** the run exits with a usage error naming the missing flag

### Requirement: Sending is opt-in

A run SHALL email no one unless `--send` is given: a digest run then emails the board, and a harvest emails source-health changes to the dev list.

#### Scenario: Digest without the flag

- **WHEN** the operator runs `weekly-digest` without `--send`
- **THEN** the digest is written to the workspace and no email is sent
