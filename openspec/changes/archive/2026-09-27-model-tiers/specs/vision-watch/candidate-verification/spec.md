## MODIFIED Requirements

### Requirement: Gate order

Each source's candidates SHALL pass these steps in order, each stopping at the first failure:

1. in the week (`out_of_window`);
2. not recorded in any earlier week (`duplicate`);
3. one triage call per source, deciding which could be a signal for a theme (`off_theme`, detail "triage"); board tips skip it;
4. when more than 8 remain, a pick of the source's 8 most notable (`source_cap`); board tips skip it;
5. URL not certainly dead, and the page scrapes (`url_404`);
6. dated (`undated`);
7. the page title refers to the same development (`title_mismatch`);
8. not a round-up (`roundup`);
9. a signal for at least one theme (`off_theme`).

Verdicts (steps 7–9) are judged up to 8 candidates per call; a lone candidate, a candidate missing from a batch answer, and each board tip are judged on their own. Board tips are exempt from steps 3, 4 and 6–9.

#### Scenario: Out of window

- **WHEN** a candidate is dated outside the week
- **THEN** it is rejected `out_of_window` without any judgement call, and when it misses by 7 days or less the audit notes how many days outside and its publish date

#### Scenario: Triage drops a candidate

- **WHEN** triage drops a candidate as a signal for no theme
- **THEN** it is rejected `off_theme` with detail "triage", and its page is never scraped

#### Scenario: Busy source

- **WHEN** 20 candidates of one source pass triage
- **THEN** 8 are picked, the other 12 are rejected `source_cap` without being scraped, and the 8 are judged in one call

### Requirement: Offline replay

`replay-gate --from W --to W` SHALL re-judge the recorded candidates of past weeks with the current gate, on the small model: findings plus `off_theme` and `source_cap` rejects. It uses cached page titles and never scrapes. `--dry-run` SHALL only print the planned judgement calls and an upper-bound estimate of input tokens. The result SHALL be written with a review report outside the live evidence. `--apply` SHALL archive `evidence/` and `clusters/` as `-v1`, install the replayed weeks and re-cluster them in order, and SHALL refuse to run twice.

#### Scenario: Dry run

- **WHEN** the operator runs `replay-gate --from 2026-W38 --to 2026-W39 --dry-run`
- **THEN** it prints the weeks, candidates, planned calls and estimated input tokens, and makes no judgement call
