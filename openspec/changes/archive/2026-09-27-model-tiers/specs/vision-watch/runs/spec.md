## MODIFIED Requirements

### Requirement: Run summary

At the end of a run the system SHALL print the week label with the number of findings and rejected items for that week, followed by one line per checked source with its status and its verified/rejected counts, after the token usage per model.

#### Scenario: Harvest summary

- **WHEN** a harvest completes
- **THEN** it prints the token usage, `week <label>: findings=<n> rejected=<m>` and one `<source>: <status> (<v>v/<r>r)` line per checked source

## ADDED Requirements

### Requirement: Nodes by model tier

The harvest SHALL run on the small model, clustering on the base model, and the weekly and monthly digests on the thinking model.

#### Scenario: Thinking model configured

- **WHEN** `LLM_THINKING_MODEL` names a stronger model than the base model
- **THEN** only the digests use it; the harvest keeps the small model
