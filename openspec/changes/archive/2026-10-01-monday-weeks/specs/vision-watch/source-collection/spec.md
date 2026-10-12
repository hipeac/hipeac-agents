## MODIFIED Requirements

### Requirement: Feed channel

A source with a feed URL SHALL be read from its RSS/Atom feed with a plain HTTP fetch, without the crawl provider and without an extraction judgement. Every entry SHALL be considered, and entries dated outside the week SHALL be dropped before any further work. Entries captured earlier in the week by `snapshot-feeds` SHALL be merged in, without duplicates. When the feed cannot be fetched or has no entries at all, the source SHALL fall back to scraping its page and be flagged `feed_fetch_failed` or `feed_empty`. When the feed's oldest entry is newer than the week's Monday and no snapshot exists, the source SHALL be flagged `feed_truncated`.

#### Scenario: Feed fetch fails

- **WHEN** a source's feed returns an error
- **THEN** the source's page (not the feed URL) is scraped and its candidates extracted, and the outcome is flagged `feed_fetch_failed`

#### Scenario: Old feed entries

- **WHEN** a feed's entries are dated before the week's Monday
- **THEN** they are dropped without being scraped or judged

#### Scenario: Empty feed

- **WHEN** a source's feed returns a valid document with no entries
- **THEN** the page is scraped instead and the outcome is flagged `feed_empty`

#### Scenario: Busy feed with a snapshot

- **WHEN** a feed reaches back only to Thursday but a snapshot holds Monday's entries
- **THEN** both are gated and the source is not flagged truncated

### Requirement: General sweep

Unless skipped, the harvest SHALL run one web search per theme (its sweep query, or its description) limited to 5 hits and bounded to the harvested week's dates. Hits already seen from another theme are ignored. The hits SHALL be triaged before any scrape, and what survives is verified like any candidate under source `sweep`.

#### Scenario: Sweep skipped

- **WHEN** the harvest runs with `--skip-sweep`
- **THEN** no web search runs and the sweep outcome is `skipped`

#### Scenario: Backfilled week

- **WHEN** a simulated harvest runs for a past week
- **THEN** each search is bounded to that week's Monday–Sunday dates

### Requirement: arXiv channel

A source with an arXiv category SHALL be read from arXiv's past-week listing page for that category, keeping the papers announced inside the week. One selection call SHALL pick at most 8 of them from their titles, as the week's most notable; only those papers' abstract pages are fetched, one a second, and stand in for the scraped page, so nothing goes through the crawl provider. The rest are recorded as rejected `off_theme`. An unreachable listing SHALL fail the source with the `feed_fetch_failed` flag.

#### Scenario: Weekend harvest

- **WHEN** a harvest runs on Monday for the week that closed on Sunday
- **THEN** that week's cs.AR announcements are read from the listing, including Sunday evening's, although arXiv's RSS feed is empty at weekends

#### Scenario: Busy category

- **WHEN** cs.RO announced 640 papers in the week
- **THEN** at most 8 reach the full verdict and only their abstracts are fetched
