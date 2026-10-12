# Spec Delta

## MODIFIED Requirements

### Requirement: Error reporting

When a Sentry DSN is configured, unhandled errors in a run SHALL be reported to Sentry, tagged with the deployed release (`GIT_REV`, when set) and the environment (`SENTRY_ENVIRONMENT`, default `development`). Log records at warning level or above SHALL be sent to Sentry as logs.

#### Scenario: Crash with Sentry configured

- **WHEN** a run fails with an unhandled error and a DSN is set
- **THEN** the error is sent to Sentry

#### Scenario: Deployed run

- **WHEN** a run fails on the server, where `GIT_REV` is `3f2a1bc` and `SENTRY_ENVIRONMENT` is `production`
- **THEN** the Sentry event carries release `3f2a1bc` and environment `production`

#### Scenario: Local run

- **WHEN** a run fails locally with a DSN set and neither `GIT_REV` nor `SENTRY_ENVIRONMENT`
- **THEN** the event carries environment `development` and no release

## ADDED Requirements

### Requirement: Scheduled run monitoring

`weekly-harvest`, `weekly-digest`, `monthly-digest` and `snapshot-feeds` SHALL accept `--check-in`. With it, and a Sentry DSN configured, the run SHALL check in with the command's Sentry cron monitor (`vision-watch-<command>`): in progress when it starts, then OK when it exits with code 0, or error when it exits with any other code or raises. The check-in SHALL carry the monitor's schedule, so the monitor is created or updated from it, and the schedules SHALL match the ones the server runs. Without `--check-in`, or without a DSN, a run SHALL send no check-in.

#### Scenario: Scheduled harvest succeeds

- **WHEN** `weekly-harvest --send --check-in` runs with a DSN and exits with code 0
- **THEN** the `vision-watch-weekly-harvest` monitor receives an in-progress check-in, then an OK check-in with the run's duration

#### Scenario: Run refuses without raising

- **WHEN** `weekly-harvest --check-in` stops with "crawl provider out of credits" and exit code 1
- **THEN** the monitor receives an error check-in

#### Scenario: Run crashes

- **WHEN** `weekly-digest --check-in` raises an unhandled error
- **THEN** the monitor receives an error check-in and the error is reported to Sentry

#### Scenario: Quiet Monday for the monthly

- **WHEN** `monthly-digest --send --check-in` runs on a Monday when no month has just completed, and exits with code 0 after doing nothing
- **THEN** the `vision-watch-monthly-digest` monitor receives an OK check-in

#### Scenario: Manual backfill

- **WHEN** the operator runs `monthly-digest --month 2026-06 --send` without `--check-in`
- **THEN** no check-in is sent

#### Scenario: Flag without a DSN

- **WHEN** `snapshot-feeds --check-in` runs with no Sentry DSN
- **THEN** it runs as without the flag and sends nothing

#### Scenario: Schedule drift

- **WHEN** the server's schedule for a command differs from its monitor's schedule
- **THEN** the test suite fails
