## MODIFIED Requirements

### Requirement: arXiv channel

A source with an arXiv category SHALL be read from arXiv's past-week listing page for that category, keeping the papers announced inside the week. One selection call SHALL pick at most 8 of them from their titles, as the week's most notable; only those papers' abstract pages are fetched, one a second, and stand in for the scraped page, so nothing goes through the crawl provider. The rest are recorded as rejected `off_theme`. An unreachable listing SHALL fail the source with the `feed_fetch_failed` flag.

#### Scenario: Weekend harvest

- **WHEN** a harvest runs on a Saturday for the week that just closed
- **THEN** that week's cs.AR announcements are read from the listing, although arXiv's RSS feed is empty at weekends

#### Scenario: Busy category

- **WHEN** cs.RO announced 640 papers in the week
- **THEN** at most 8 reach the full verdict and only their abstracts are fetched
