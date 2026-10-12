# runs Specification

## Purpose

How an operator runs vision-watch from the command line: which commands exist, which editorial week a run targets, which knobs slice a run, and what a run reports back.

## Requirements

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

### Requirement: Workspace override

`--data-dir PATH` SHALL point a run at a different workspace root for that run only, for every command.

#### Scenario: Harvest against a scratch workspace

- **WHEN** the operator runs a harvest with `--data-dir /tmp/scratch`
- **THEN** all evidence is read from and written under `/tmp/scratch`, and the configured workspace is untouched

### Requirement: Partial harvests

A harvest SHALL accept `--limit N` (check at most N due sources), `--only id1,id2` (check only these sources) and `--skip-sweep` (drop the per-theme web sweep), so an operator can run cheap partial harvests. With `--only`, the unattributed inbox, the board tips and the sweep SHALL run only when named (`inbox`, `board-tip`, `sweep`), and newsletters of sources left out SHALL not be read.

#### Scenario: Limited harvest

- **WHEN** the operator runs a harvest with `--limit 4 --skip-sweep`
- **THEN** only the first 4 due sources are checked and no web sweep runs

#### Scenario: Only some sources

- **WHEN** the operator runs a harvest with `--only arxiv-cs-ar`
- **THEN** no newsletter, tip or sweep is processed

### Requirement: Sending is opt-in

A run SHALL email no one unless `--send` is given: a digest run then emails the board, and a harvest emails source-health changes to the dev list.

#### Scenario: Digest without the flag

- **WHEN** the operator runs `weekly-digest` without `--send`
- **THEN** the digest is written to the workspace and no email is sent

### Requirement: Required configuration

A run SHALL refuse to start without an LLM provider key, printing that no provider is configured and exiting with a non-zero code. A run SHALL fail with a clear message naming the missing file when the workspace has no `config/themes.yaml` or `config/source-catalog.yaml`. Services that are not configured SHALL be listed as skipped rather than failing the run.

#### Scenario: No LLM key

- **WHEN** a run starts with neither an OpenAI nor an Anthropic API key set
- **THEN** it prints "no LLM provider configured" and exits with code 1

#### Scenario: Mail not configured

- **WHEN** a run starts without mail credentials
- **THEN** it prints that mail was skipped (not configured) and continues

### Requirement: Crawl credit preflight

A run that crawls SHALL check the crawl provider before collecting and stop with "crawl provider out of credits" (exit code 1) when the provider has no credits left, instead of failing source by source. Runs that do not crawl SHALL not spend crawl credits or be blocked by the crawl provider's quota.

#### Scenario: Out of credits before a harvest

- **WHEN** a harvest starts and the crawl provider reports insufficient credits
- **THEN** the run prints "crawl provider out of credits" and exits with code 1 before checking any source

### Requirement: Run summary

At the end of a run the system SHALL print the week label with the number of findings and rejected items for that week, followed by one line per checked source with its status and its verified/rejected counts, after the token usage per model.

#### Scenario: Harvest summary

- **WHEN** a harvest completes
- **THEN** it prints the token usage, `week <label>: findings=<n> rejected=<m>` and one `<source>: <status> (<v>v/<r>r)` line per checked source

### Requirement: Redoing a week

`--redo` on a harvest or weekly digest SHALL set the week aside before running, and it SHALL do so only after the run's configuration checks pass. It moves the week's digest and grouping into `_backup/<week>-<timestamp>/`, plus the whole evidence folder for a harvest. It backs up every cluster log with entries for that week, then removes those entries, dropping clusters left empty. A digest's sent marker SHALL stay, so a redone week is never mailed twice.

#### Scenario: Digest redo

- **WHEN** the operator runs `weekly-digest --on 2026-09-25 --redo`
- **THEN** the W39 digest, grouping and cluster entries are backed up and cleared, the findings stay, and the week is regrouped and recomposed

#### Scenario: Redone week already sent

- **WHEN** a week whose digest was sent is redone and recomposed with `--send`
- **THEN** no email is sent

### Requirement: Nodes by model tier

The harvest SHALL run on the small model, clustering on the base model, and the weekly and monthly digests on the thinking model.

#### Scenario: Thinking model configured

- **WHEN** `LLM_THINKING_MODEL` names a stronger model than the base model
- **THEN** only the digests use it; the harvest keeps the small model
