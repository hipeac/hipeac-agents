## MODIFIED Requirements

### Requirement: Due sources

Every source in the human-owned source catalog SHALL be checked every week, including foresight and community sources. Sources marked skipped stay due so they are reported rather than silently missing.

#### Scenario: Signals source

- **WHEN** the catalog lists a foresight source (formerly the unread signals stream)
- **THEN** the harvest checks it like any other source

### Requirement: Bot-protected sources

A source with a `skip` reason SHALL not be fetched and SHALL be reported as `blocked`, with the reason as detail.

#### Scenario: Blocked source

- **WHEN** a due source declares `skip: bot-protected; no alternative feed yet`
- **THEN** its outcome is `blocked` with detail "skipped: bot-protected; no alternative feed yet"

## ADDED Requirements

### Requirement: Catalog format

The catalog SHALL group sources under their class. A `classes` map sets each class's default tier (a confidence ceiling) and independence, which a source inherits unless it overrides them. A source SHALL need only an id and a URL. Its region defaults to global and its name to its id. `senders` makes it a newsletter, and `web: false` makes it newsletter-only.

#### Scenario: Class defaults

- **WHEN** a `programmes` source declares only id and URL and the class default is tier 2, high independence
- **THEN** the source is tier 2 with high independence, region global

#### Scenario: Class without defaults

- **WHEN** a source's class has no defaults and the source declares no tier
- **THEN** reading the catalog fails
