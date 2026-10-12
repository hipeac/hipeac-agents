## ADDED Requirements

### Requirement: Digest needs a harvest

`weekly-digest` SHALL refuse to run for a week that has no completed harvest record. It SHALL exit non-zero with a message naming the week and `weekly-harvest`, and SHALL write no digest, make no model call and send no email. A week that already has a recorded digest (unless it is being redone), and `--intro-only`, SHALL NOT be subject to this check.

#### Scenario: Digest without a harvest

- **WHEN** operator runs `weekly-digest --send` for a week with no harvest record
- **THEN** exit code is non-zero, the message says to run `weekly-harvest` for that week first, and no digest is written or sent

#### Scenario: Digest after a harvest

- **WHEN** operator runs `weekly-digest` for a week whose harvest completed, even with zero findings
- **THEN** the digest is composed as usual

#### Scenario: Sending a recorded digest

- **WHEN** a week has a recorded digest and operator runs `weekly-digest --send`
- **THEN** the check does not apply and the recorded digest is sent once

#### Scenario: Redo without a harvest

- **WHEN** operator runs `weekly-digest --redo` for a week whose harvest record was cleared
- **THEN** the run is refused before the week is set aside
