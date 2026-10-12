## MODIFIED Requirements

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

### Requirement: One development, one finding

Findings that share a URL SHALL fold into one: the most significant wins (a figure breaks ties), and the others' summaries become its corroboration. Findings from different outlets about the same underlying event (same entities, numbers and date) SHALL fold into the most significant one. Each folded finding is recorded as rejected `duplicate`, noting the near-match rule. A newsletter finding published before the week that reports the same event as one of the previous week's findings SHALL be rejected `duplicate`, naming that week and finding; the previous week's finding is left as it is.

#### Scenario: Two outlets, one event

- **WHEN** two sources report the same announcement under different URLs
- **THEN** one finding is kept, with the other's summary as corroboration, and the other is recorded as `duplicate`

#### Scenario: Late item already in last week's digest

- **WHEN** a newsletter item published before the week reports the same announcement as a finding of the previous week, under a different URL
- **THEN** it is recorded as `duplicate` with detail naming the previous week and finding, and does not reach this week's digest
