## ADDED Requirements

### Requirement: Redoing a week

`--redo` on a harvest or weekly digest SHALL set the week aside before running, and it SHALL do so only after the run's configuration checks pass. It moves the week's digest and grouping into `_backup/<week>-<timestamp>/`, plus the whole evidence folder for a harvest. It backs up every cluster log with entries for that week, then removes those entries, dropping clusters left empty. A digest's sent marker SHALL stay, so a redone week is never mailed twice.

#### Scenario: Digest redo

- **WHEN** the operator runs `weekly-digest --on 2026-09-25 --redo`
- **THEN** the W39 digest, grouping and cluster entries are backed up and cleared, the findings stay, and the week is regrouped and recomposed

#### Scenario: Redone week already sent

- **WHEN** a week whose digest was sent is redone and recomposed with `--send`
- **THEN** no email is sent
