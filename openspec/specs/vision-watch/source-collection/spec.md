# source-collection Specification

## Purpose

How a weekly harvest gathers candidate developments from the source catalog, the newsletter/tips mailbox and a general web sweep, and reports how each source fared.

## Requirements

### Requirement: Due sources

Every source in the human-owned source catalog SHALL be checked every week, whatever its class, including foresight and commentary sources. Sources marked skipped stay due so they are reported rather than silently missing.

#### Scenario: Signals source

- **WHEN** the catalog lists a foresight source (formerly the unread signals stream)
- **THEN** the harvest checks it like any other source

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

### Requirement: Page channel

A source without a feed SHALL have its listing page scraped through the crawl provider, and up to 10 candidate developments SHALL be extracted from the first 12,000 characters of the page. Each has a title, URL, date when present, one-sentence summary and notable figure. Extraction SHALL prefer the newest dated items over featured or pinned ones.

#### Scenario: Scrape fails

- **WHEN** the listing page cannot be scraped
- **THEN** the source is reported as failed with the URL that failed

### Requirement: Newsletters and tips mailbox

The harvest SHALL read the week's messages from the harvest mailbox once, then route each message: messages addressed to the board-tip mailbox are board tips; otherwise a message goes to the newsletter source whose declared senders match its sender (case-insensitive substring either way); messages from no known sender go to an `inbox` bucket that is harvested as newsletter content. A message without a sender SHALL match no source.

#### Scenario: Newsletter headline not in the body

- **WHEN** a candidate extracted from a newsletter has a headline that does not appear in the newsletter body
- **THEN** it is rejected as `newsletter_mismatch`

#### Scenario: Unknown sender

- **WHEN** a message comes from a sender no catalog source declares
- **THEN** its candidates are harvested under source `inbox`

### Requirement: Board tips

A board tip SHALL be treated as an editor-flagged lead. Its first link is verified like any candidate. It SHALL always receive the closest theme even when it fits none, skip triage and the date, title and round-up checks, and be credited to its original author. When a forwarded message quotes an original `From:` line, that person is credited rather than the forwarder.

#### Scenario: Tip without a link

- **WHEN** a board tip contains no link
- **THEN** it is recorded as rejected `board_tip_unresolved`, naming who sent it

#### Scenario: Verified tip

- **WHEN** a board tip's link verifies
- **THEN** the finding is recorded under source `board-tip` with "[flagged by <name>]" appended to its summary

### Requirement: General sweep

Unless skipped, the harvest SHALL run one web search per theme (its sweep query, or its description) limited to 5 hits and bounded to the harvested week's dates. Hits already seen from another theme are ignored. The hits SHALL be triaged before any scrape, and what survives is verified like any candidate under source `sweep`.

#### Scenario: Sweep skipped

- **WHEN** the harvest runs with `--skip-sweep`
- **THEN** no web search runs and the sweep outcome is `skipped`

#### Scenario: Backfilled week

- **WHEN** a simulated harvest runs for a past week
- **THEN** each search is bounded to that week's Monday–Sunday dates

### Requirement: Bot-protected sources

A source with a `skip` reason SHALL not be fetched and SHALL be reported as `blocked`, with the reason as detail.

#### Scenario: Blocked source

- **WHEN** a due source declares `skip: bot-protected; no alternative feed yet`
- **THEN** its outcome is `blocked` with detail "skipped: bot-protected; no alternative feed yet"

### Requirement: Source outcomes

Every checked source SHALL end the harvest with exactly one outcome under its own id, from `collected`, `empty`, `failed`, `blocked` or `skipped`, with its verified and rejected counts and any channel flags. A source that produced only rejected candidates counts as `collected`, in every channel.

#### Scenario: Channel error

- **WHEN** checking a source raises an unexpected error
- **THEN** that source's outcome is `failed` under its own id, with the error as detail

### Requirement: Scrape cache

Every page fetched through the crawl provider SHALL be cached in the workspace, keyed by its canonical URL (tracking parameters stripped), and reused across weeks and runs. Feeds SHALL never be cached, and the re-sample check SHALL always fetch fresh.

#### Scenario: Page seen last week

- **WHEN** a candidate's URL was already scraped in an earlier run
- **THEN** the cached page is used and no crawl credit is spent

### Requirement: arXiv channel

A source with an arXiv category SHALL be read from arXiv's past-week listing page for that category, keeping the papers announced inside the week. One selection call SHALL pick at most 8 of them from their titles, as the week's most notable; only those papers' abstract pages are fetched, one a second, and stand in for the scraped page, so nothing goes through the crawl provider. The rest are recorded as rejected `off_theme`. An unreachable listing SHALL fail the source with the `feed_fetch_failed` flag.

#### Scenario: Weekend harvest

- **WHEN** a harvest runs on Monday for the week that closed on Sunday
- **THEN** that week's cs.AR announcements are read from the listing, including Sunday evening's, although arXiv's RSS feed is empty at weekends

#### Scenario: Busy category

- **WHEN** cs.RO announced 640 papers in the week
- **THEN** at most 8 reach the full verdict and only their abstracts are fetched

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

### Requirement: Catalog format

The catalog SHALL declare its source classes in a `classes` map and group every source under one of them. A class is a kind of voice, meaning who is speaking, not a channel: a newsletter belongs to the class of whoever writes it. Each class SHALL carry a one-line `about`. `primary: false` SHALL mark a class that reports or comments on others' news rather than announcing its own; classes are primary by default. A class MAY set a `weekly_cap`. A source SHALL need only an id and a URL. Its region defaults to global and its name to its id. `senders` makes it a newsletter, and `web: false` makes it newsletter-only. A catalog that still declares independence, per class or per source, SHALL still read; the value is ignored.

#### Scenario: Class defaults

- **WHEN** a `programmes` source declares only id and URL, and `programmes` is declared without `primary`
- **THEN** the source is in class programmes, a primary class, region global, named by its id

#### Scenario: Class without defaults

- **WHEN** a source is grouped under a class the `classes` map does not declare
- **THEN** reading the catalog fails, naming the class

#### Scenario: Newsletter keeps its writer's class

- **WHEN** SemiAnalysis, in class `analysis`, arrives both by feed and by email
- **THEN** its findings from both channels count as `analysis`

#### Scenario: Legacy independence

- **WHEN** a class declares `independence: low` and a source overrides `independence: high`
- **THEN** the catalog reads and neither value affects any ranking

### Requirement: Class volume cap

A catalog class MAY set a weekly cap. The verified findings of that class's sources together SHALL keep at most that many per week, ranked by significance, then recency. The overflow SHALL be recorded as rejected `source_cap`, with a detail naming the class cap. A class without a cap is not limited as a class.

#### Scenario: Busy week for AI newsletters

- **WHEN** `ai-news` has a weekly cap of 6 and its sources verify 11 findings
- **THEN** the 6 strongest are kept and the other 5 are recorded as `source_cap` with a class-cap detail

#### Scenario: Uncapped class

- **WHEN** `press` sets no weekly cap and one press source verifies 9 findings
- **THEN** all 9 are kept
