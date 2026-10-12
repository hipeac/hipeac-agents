## MODIFIED Requirements

### Requirement: Stale entries after a redo

When a week's evidence is redone, the cluster logs SHALL end up describing the week's current findings only. No entry may point at a finding id that now refers to a different finding. A harvest SHALL refuse to run, before spending anything, while the week still has cluster entries from an earlier harvest, and SHALL name `--redo` as the way forward.

#### Scenario: Week harvested again

- **WHEN** a week's evidence is replaced with `--redo` and its digest recomposed
- **THEN** every cluster entry for that week carries the title of the finding its id refers to

#### Scenario: Re-harvest without redo

- **WHEN** a harvest runs for a week whose evidence was moved away by hand but whose cluster entries remain
- **THEN** it stops with a message pointing to `--redo`, without scraping or judging anything
