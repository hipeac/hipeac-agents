## MODIFIED Requirements

### Requirement: General sweep

Unless skipped, the harvest SHALL run one web search per watch question (its sweep query, or the question itself) limited to 5 hits and bounded to the harvested week's dates. Hits already seen from another question are ignored. The hits SHALL be triaged before any scrape, and what survives is verified like any candidate under source `sweep`.

#### Scenario: Sweep skipped

- **WHEN** the harvest runs with `--skip-sweep`
- **THEN** no web search runs and the sweep outcome is `skipped`

#### Scenario: Backfilled week

- **WHEN** a simulated harvest runs for a past week
- **THEN** each search is bounded to that week's Saturday–Friday dates
