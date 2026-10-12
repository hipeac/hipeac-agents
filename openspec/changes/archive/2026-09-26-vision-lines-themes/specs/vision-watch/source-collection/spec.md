## MODIFIED Requirements

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
- **THEN** each search is bounded to that week's Saturday–Friday dates
