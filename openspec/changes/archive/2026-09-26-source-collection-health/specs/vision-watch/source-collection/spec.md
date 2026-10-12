## MODIFIED Requirements

### Requirement: Feed channel

A source with a feed URL SHALL be read from its RSS/Atom feed with a plain HTTP fetch, without the crawl provider and without an extraction judgement. Every entry SHALL be considered, and entries dated outside the week SHALL be dropped before any further work. Entries captured earlier in the week by `snapshot-feeds` SHALL be merged in, without duplicates. When the feed cannot be fetched or has no entries at all, the source SHALL fall back to scraping its page and be flagged `feed_fetch_failed` or `feed_empty`. When the feed's oldest entry is newer than the week's Saturday and no snapshot exists, the source SHALL be flagged `feed_truncated`.

#### Scenario: Feed fetch fails

- **WHEN** a source's feed returns an error
- **THEN** the source's page (not the feed URL) is scraped and its candidates extracted, and the outcome is flagged `feed_fetch_failed`

#### Scenario: Old feed entries

- **WHEN** a feed's entries are dated before the week's Saturday
- **THEN** they are dropped without being scraped or judged

#### Scenario: Empty feed

- **WHEN** a source's feed returns a valid document with no entries
- **THEN** the page is scraped instead and the outcome is flagged `feed_empty`

#### Scenario: Busy feed with a snapshot

- **WHEN** a feed reaches back only to Wednesday but a snapshot holds Saturday's entries
- **THEN** both are gated and the source is not flagged truncated

### Requirement: Page channel

A source without a feed SHALL have its listing page scraped through the crawl provider, and up to 10 candidate developments SHALL be extracted from the first 12,000 characters of the page. Each has a title, URL, date when present, one-sentence summary and notable figure. Extraction SHALL prefer the newest dated items over featured or pinned ones.

#### Scenario: Scrape fails

- **WHEN** the listing page cannot be scraped
- **THEN** the source is reported as failed with the URL that failed

### Requirement: Source outcomes

Every checked source SHALL end the harvest with exactly one outcome under its own id, from `collected`, `empty`, `failed`, `blocked` or `skipped`, with its verified and rejected counts and any channel flags. A source that produced only rejected candidates counts as `collected`, in every channel.

#### Scenario: Channel error

- **WHEN** checking a source raises an unexpected error
- **THEN** that source's outcome is `failed` under its own id, with the error as detail

## ADDED Requirements

### Requirement: arXiv channel

A source with an arXiv category SHALL be read through the arXiv API for submissions dated inside the week, 200 results per page, one request every three seconds. It is not scraped: the API's title, abstract and date stand in for the page. An unreachable API SHALL fail the source with the `feed_fetch_failed` flag.

#### Scenario: Weekend harvest

- **WHEN** a harvest runs on a Saturday for the week that just closed
- **THEN** the week's cs.AR submissions are gated, although arXiv's RSS feed is empty at weekends

### Requirement: Daily feed snapshots

`snapshot-feeds` SHALL fetch every feed source (not arXiv, not skipped), keep the entries dated inside the week open that day, and merge them with the week's earlier snapshot by canonical URL. Snapshots SHALL survive a `--redo` of the week.

#### Scenario: Two snapshots in one week

- **WHEN** snapshots run on Monday and Wednesday of the same week
- **THEN** the week's snapshot holds the union of both days' in-week entries

### Requirement: Source health

After each harvest, every checked catalog source SHALL be labelled, most urgent first:

- `skipped`: never checked;
- `fetch_failed`: failed, or its feed was unreachable;
- `empty_feed`, `truncated_feed`: from the channel flags;
- `stale_listing`: only out-of-window candidates for 3 weeks in a row;
- `silent`: no candidates at all for 3 weeks in a row;
- `ok` otherwise.

The labels and a readable report SHALL be written to the week's evidence. With `--send`, the report SHALL be emailed to the dev list (`dev@hipeac.net` by default) only when the set of unhealthy sources differs from the last report.

#### Scenario: New broken feed

- **WHEN** a harvest with `--send` finds a feed empty that was fine last week
- **THEN** the health report lists it under `empty_feed` and the dev list receives the report

#### Scenario: Nothing changed

- **WHEN** the same sources are unhealthy as in the last report
- **THEN** the report says "unchanged" and no email is sent
