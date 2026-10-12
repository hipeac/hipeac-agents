# candidate-verification Specification

## Purpose

How each harvested candidate is checked before it becomes a finding, and how a week's evidence is recorded (verified findings plus an audit of everything rejected) so the editorial board can trust and inspect it.

## Requirements

### Requirement: Gate order

Each source's candidates SHALL pass these steps in order, each stopping at the first failure:

1. in the week, or, for a newsletter item, from a newsletter received in the week and published at most 7 days before it (`out_of_window`);
2. not recorded in any earlier week (`duplicate`); a newsletter item published before the week is also checked against the previous week's findings, below;
3. one triage call per source, deciding which could be a signal for a theme (`off_theme`, detail "triage"); board tips skip it;
4. when more than 8 remain, a pick of the source's 8 most notable (`source_cap`); board tips skip it;
5. a newsletter's click-tracker or web view followed to the story, the URL not certainly dead, and the page scrapes (`url_404`); a page that is still a tracker or web view, an image or an error page is rejected (`unresolved_link`);
6. dated (`undated`);
7. the page title refers to the same development (`title_mismatch`);
8. not a round-up (`roundup`);
9. a signal for at least one theme (`off_theme`).

Verdicts (steps 7–9) are judged up to 8 candidates per call; a lone candidate, a candidate missing from a batch answer, and each board tip are judged on their own. Board tips are exempt from steps 3, 4 and 6–9.

#### Scenario: Out of window

- **WHEN** a candidate is dated outside the week
- **THEN** it is rejected `out_of_window` without any judgement call, and when it misses by 7 days or less the audit notes how many days outside and its publish date

#### Scenario: Newsletter reports last week's news

- **WHEN** a newsletter received on Tuesday 22 September reports an item published on Friday 18 September, and no earlier week recorded it
- **THEN** it passes the window check for W39 and is judged like any candidate

#### Scenario: Newsletter item older than a week

- **WHEN** a newsletter received on Tuesday 22 September reports an item published on Monday 14 September, 8 days earlier
- **THEN** it is rejected `out_of_window`, with the days outside and its publish date in the audit

#### Scenario: Triage drops a candidate

- **WHEN** triage drops a candidate as a signal for no theme
- **THEN** it is rejected `off_theme` with detail "triage", and its page is never scraped

#### Scenario: Busy source

- **WHEN** 20 candidates of one source pass triage
- **THEN** 8 are picked, the other 12 are rejected `source_cap` without being scraped, and the 8 are judged in one call

#### Scenario: Newsletter tracker

- **WHEN** a newsletter candidate links `https://4ntll.r.sp1-brevo.net/mk/cl/…`, whose page redirects by meta refresh to an eu-startups.com article
- **THEN** the article is scraped and judged, and the finding records its URL without `utm_*` parameters

#### Scenario: Tracker with no story behind it

- **WHEN** a candidate's link ends on a newsletter's "view in browser" page, a thumbnail image or `?err=404`
- **THEN** it is rejected `unresolved_link`, with the URL reached as detail

### Requirement: Judgement verdict

For every candidate that reaches judgement, one model verdict SHALL assign:

- the themes it is a signal for;
- a horizon (now, 1–2 years, 3–5 years);
- a forward note of at most 160 characters on what it could change for computing in Europe;
- the single most notable figure;
- whether it is a round-up;
- a summary of at most 160 characters;
- a significance from 1 to 5 for how much it tells about where computing is heading, picking the lower score when torn.

#### Scenario: Verified candidate

- **WHEN** the verdict names at least one known theme, the title matches and it is not a round-up
- **THEN** a finding is recorded with the themes, horizon, forward note, figure, summary and significance

### Requirement: Undated candidates

A candidate with no date in the feed, extraction or text SHALL take the page's published date when the scrape provides one, and SHALL be re-checked against the week. A candidate with no date anywhere SHALL be rejected `undated`, except board tips. A newsletter item without its own date SHALL take its message's date.

#### Scenario: Date found on the page

- **WHEN** a candidate has no date but the scraped page reports one outside the week
- **THEN** it is rejected `out_of_window`

#### Scenario: No date anywhere

- **WHEN** a scraped page carries no date and neither did the candidate
- **THEN** it is rejected `undated`

### Requirement: One development, one finding

Findings that share a URL SHALL fold into one: the most significant wins (a figure breaks ties), and the others' summaries become its corroboration. Findings from different outlets about the same underlying event (same entities, numbers and date) SHALL fold into the most significant one. Each folded finding is recorded as rejected `duplicate`, noting the near-match rule. A newsletter finding published before the week that reports the same event as one of the previous week's findings SHALL be rejected `duplicate`, naming that week and finding; the previous week's finding is left as it is.

#### Scenario: Two outlets, one event

- **WHEN** two sources report the same announcement under different URLs
- **THEN** one finding is kept, with the other's summary as corroboration, and the other is recorded as `duplicate`

#### Scenario: Late item already in last week's digest

- **WHEN** a newsletter item published before the week reports the same announcement as a finding of the previous week, under a different URL
- **THEN** it is recorded as `duplicate` with detail naming the previous week and finding, and does not reach this week's digest

### Requirement: Re-sample check

About 20% of the week's findings SHALL be fetched again fresh before recording. A finding whose URL no longer resolves SHALL be moved to the audit as `url_404`, so findings and audit never disagree. Running out of crawl credits during this check SHALL not discard the week's work.

#### Scenario: Link died

- **WHEN** a sampled finding's URL fails on the fresh fetch
- **THEN** it is removed from findings and recorded as `url_404`

### Requirement: Weekly evidence files

A harvest SHALL write `evidence/<week>/findings.json` (findings numbered `f-<week>-01` onward) and `evidence/<week>/rejected.json` (every rejected candidate with URL, claimed title, source, reason and detail). Nothing SHALL be dropped silently. Both files SHALL be write-once.

#### Scenario: Every reject has a reason

- **WHEN** a candidate fails any check
- **THEN** it appears in the week's rejected file with one of the documented reasons

### Requirement: Harvested weeks replay

A harvest for a week that already has evidence SHALL replay the recorded evidence instead of collecting again, and report a single `harvest: skipped` outcome.

#### Scenario: Harvest run twice

- **WHEN** `weekly-harvest` runs for a week that already has `findings.json`
- **THEN** it prints "already harvested; replaying recorded evidence", spends nothing and writes nothing

### Requirement: Themes

Each theme in `themes.yaml` SHALL be one of the Vision's broad lines: an id, an optional title readers see (the id when absent), a plain-words description, optional open questions the next Vision asks in it, what to look for (real-world names), optional keyword hints and a sweep query. Every judgement SHALL see all themes. Clusters are keyed by theme id, in file order. Each open question SHALL be addressed as `<theme id>.<n>`, n counting from 1 in file order.

#### Scenario: Unknown question id

- **WHEN** a verdict names a theme id not in `themes.yaml`
- **THEN** that id is ignored, and a candidate left with none is rejected `off_theme`

#### Scenario: Question ids

- **WHEN** the `agentic-ai` theme lists three questions
- **THEN** they are `agentic-ai.1`, `agentic-ai.2` and `agentic-ai.3`, in file order

### Requirement: Offline replay

`replay-gate --from W --to W` SHALL re-judge the recorded candidates of past weeks with the current gate, on the small model: findings plus `off_theme` and `source_cap` rejects. It uses cached page titles and never scrapes. `--dry-run` SHALL only print the planned judgement calls and an upper-bound estimate of input tokens. The result SHALL be written with a review report outside the live evidence. `--apply` SHALL archive `evidence/` and `clusters/` as `-v1`, install the replayed weeks and re-cluster them in order, and SHALL refuse to run twice.

#### Scenario: Dry run

- **WHEN** the operator runs `replay-gate --from 2026-W38 --to 2026-W39 --dry-run`
- **THEN** it prints the weeks, candidates, planned calls and estimated input tokens, and makes no judgement call
