## MODIFIED Requirements

### Requirement: Judgement verdict

For every candidate that reaches judgement, one model verdict SHALL assign:

- the themes it is a signal for;
- a direction: accelerates the trend the Vision describes (strengthens), slows or contradicts it (weakens), or opens something the Vision does not yet cover (new);
- a horizon (now, 1–2 years, 3–5 years);
- a forward note of at most 160 characters on what it could change for computing in Europe;
- the single most notable figure;
- whether it is a round-up;
- a summary of at most 160 characters;
- a significance from 1 to 5 for how much it tells about where computing is heading, picking the lower score when torn.

#### Scenario: Verified candidate

- **WHEN** the verdict names at least one known theme, the title matches and it is not a round-up
- **THEN** a finding is recorded with the themes, direction, horizon, forward note, figure, summary and significance

### Requirement: One development, one finding

Findings that share a URL SHALL fold into one: the most significant wins (a figure breaks ties), and the others' summaries become its corroboration. Findings from different outlets about the same underlying event (same entities, numbers and date) SHALL fold into the most significant one. Each folded finding is recorded as rejected `duplicate`, noting the near-match rule.

#### Scenario: Two outlets, one event

- **WHEN** two sources report the same announcement under different URLs
- **THEN** one finding is kept, with the other's summary as corroboration, and the other is recorded as `duplicate`

## REMOVED Requirements

### Requirement: Tier ceiling

**Reason**: The evidence tier is dropped; significance, source class and independence carry what it meant.
**Migration**: Remove `tier` from catalog classes and sources; recorded files that still carry it are read and the field ignored.
