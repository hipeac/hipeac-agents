## MODIFIED Requirements

### Requirement: Due sources

Every source in the human-owned source catalog SHALL be checked every week, whatever its class, including foresight and commentary sources. Sources marked skipped stay due so they are reported rather than silently missing.

#### Scenario: Signals source

- **WHEN** the catalog lists a foresight source (formerly the unread signals stream)
- **THEN** the harvest checks it like any other source

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

## ADDED Requirements

### Requirement: Class volume cap

A catalog class MAY set a weekly cap. After each source's own volume cap, the sources of that class together SHALL keep at most that many findings per week, ranked by significance, then recency. The overflow SHALL be recorded as rejected `source_cap`, with a detail naming the class cap. A class without a cap is not limited as a class.

#### Scenario: Busy week for AI newsletters

- **WHEN** `ai-news` has a weekly cap of 6 and its sources keep 11 findings after their own caps
- **THEN** the 6 strongest are kept and the other 5 are recorded as `source_cap` with a class-cap detail

#### Scenario: Uncapped class

- **WHEN** `press` sets no weekly cap and its sources keep 9 findings after their own caps
- **THEN** all 9 are kept
