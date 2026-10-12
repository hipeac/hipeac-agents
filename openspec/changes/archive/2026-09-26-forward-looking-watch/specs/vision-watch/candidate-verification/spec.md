## MODIFIED Requirements

### Requirement: Gate order

Each source's candidates SHALL pass these steps in order, each stopping at the first failure:

1. in the week (`out_of_window`);
2. not recorded in any earlier week (`duplicate`);
3. one triage call per source, deciding which could move a watch question (`off_theme`, detail "triage"); board tips skip it;
4. URL not certainly dead, and the page scrapes (`url_404`);
5. dated (`undated`);
6. the page title refers to the same development (`title_mismatch`);
7. not a round-up (`roundup`);
8. moves at least one watch question (`off_theme`).

Board tips are exempt from steps 3 and 5–8.

#### Scenario: Out of window

- **WHEN** a candidate is dated outside the week
- **THEN** it is rejected `out_of_window` without any judgement call, and when it misses by 7 days or less the audit notes how many days outside and its publish date

#### Scenario: Triage drops a candidate

- **WHEN** triage drops a candidate as moving no watch question
- **THEN** it is rejected `off_theme` with detail "triage", and its page is never scraped

### Requirement: Judgement verdict

For every candidate that reaches judgement, one model verdict SHALL assign:

- the watch questions it moves;
- a direction (strengthens, weakens, or opens something new);
- a horizon (now, 1–2 years, 3–5 years);
- a forward note of at most 160 characters on what it could change for European computing;
- an evidence tier as confidence only: 1 peer-reviewed or reproducible, 2 committed reality, 3 stated intention, 4 commentary;
- the single most notable figure;
- whether it is a round-up;
- a summary of at most 160 characters;
- a significance from 1 to 5 as forward importance for Europe, picking the lower score when torn.

#### Scenario: Verified candidate

- **WHEN** the verdict names at least one known watch question, the title matches and it is not a round-up
- **THEN** a finding is recorded with the questions, direction, horizon, forward note, tier, figure, summary and significance

### Requirement: Undated candidates

A candidate with no date in the feed, extraction or text SHALL take the page's published date when the scrape provides one, and SHALL be re-checked against the week. A candidate with no date anywhere SHALL be rejected `undated`, except board tips. A newsletter item without its own date SHALL take its message's date.

#### Scenario: Date found on the page

- **WHEN** a candidate has no date but the scraped page reports one outside the week
- **THEN** it is rejected `out_of_window`

#### Scenario: No date anywhere

- **WHEN** a scraped page carries no date and neither did the candidate
- **THEN** it is rejected `undated`

## REMOVED Requirements

### Requirement: Keyword matching

**Reason**: The keyword pre-filter is replaced by batched triage on the watch questions.
**Migration**: `keywords` in `themes.yaml` become optional hints shown to the judgement calls.

## ADDED Requirements

### Requirement: Watch questions

Each theme in `themes.yaml` SHALL be a watch question: an id, the question, why it matters, what to look for (real-world names), optional keyword hints and a sweep query. Every judgement SHALL see all questions. Clusters and digest sections are keyed by question id, in file order.

#### Scenario: Unknown question id

- **WHEN** a verdict names a question id not in `themes.yaml`
- **THEN** that id is ignored, and a candidate left with none is rejected `off_theme`

### Requirement: Offline replay

`replay-gate --from W --to W` SHALL re-judge the recorded candidates of past weeks with the current gate: findings plus `off_theme` and `source_cap` rejects. It uses cached page titles and never scrapes. `--dry-run` SHALL only print the planned judgement calls. The result SHALL be written with a review report outside the live evidence. `--apply` SHALL archive `evidence/` and `clusters/` as `-v1`, install the replayed weeks and re-cluster them in order, and SHALL refuse to run twice.

#### Scenario: Dry run

- **WHEN** the operator runs `replay-gate --from 2026-W26 --to 2026-W39 --dry-run`
- **THEN** it prints the weeks, candidates and planned calls, and makes no judgement call
