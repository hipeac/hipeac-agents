## RENAMED Requirements

- FROM: `### Requirement: Watch questions`
- TO: `### Requirement: Themes`

## MODIFIED Requirements

### Requirement: Themes

Each theme in `themes.yaml` SHALL be one of the Vision's broad lines: an id, a plain-words description, optional open questions the next Vision asks in it, what to look for (real-world names), optional keyword hints and a sweep query. Every judgement SHALL see all themes. Clusters and digest sections are keyed by theme id, in file order.

#### Scenario: Unknown question id

- **WHEN** a verdict names a theme id not in `themes.yaml`
- **THEN** that id is ignored, and a candidate left with none is rejected `off_theme`

### Requirement: Gate order

Each source's candidates SHALL pass these steps in order, each stopping at the first failure:

1. in the week (`out_of_window`);
2. not recorded in any earlier week (`duplicate`);
3. one triage call per source, deciding which could be a signal for a theme (`off_theme`, detail "triage"); board tips skip it;
4. URL not certainly dead, and the page scrapes (`url_404`);
5. dated (`undated`);
6. the page title refers to the same development (`title_mismatch`);
7. not a round-up (`roundup`);
8. a signal for at least one theme (`off_theme`).

Board tips are exempt from steps 3 and 5–8.

#### Scenario: Out of window

- **WHEN** a candidate is dated outside the week
- **THEN** it is rejected `out_of_window` without any judgement call, and when it misses by 7 days or less the audit notes how many days outside and its publish date

#### Scenario: Triage drops a candidate

- **WHEN** triage drops a candidate as a signal for no theme
- **THEN** it is rejected `off_theme` with detail "triage", and its page is never scraped

### Requirement: Judgement verdict

For every candidate that reaches judgement, one model verdict SHALL assign:

- the themes it is a signal for;
- a direction: accelerates the trend the Vision describes (strengthens), slows or contradicts it (weakens), or opens something the Vision does not yet cover (new);
- a horizon (now, 1–2 years, 3–5 years);
- a forward note of at most 160 characters on what it could change for computing in Europe;
- an evidence tier as confidence only: 1 peer-reviewed or reproducible, 2 committed reality, 3 stated intention, 4 commentary;
- the single most notable figure;
- whether it is a round-up;
- a summary of at most 160 characters;
- a significance from 1 to 5 for how much it tells about where computing is heading, picking the lower score when torn.

#### Scenario: Verified candidate

- **WHEN** the verdict names at least one known theme, the title matches and it is not a round-up
- **THEN** a finding is recorded with the themes, direction, horizon, forward note, tier, figure, summary and significance
