## MODIFIED Requirements

### Requirement: Per-source volume cap

A single source SHALL contribute at most 4 findings per week. When a source verifies more than 4, it SHALL keep those with significance 4 or higher, keep at least its top 2, and cap at 4. Ranking is by significance, then recency. The overflow SHALL be recorded as rejected `source_cap`.

#### Scenario: High-volume source

- **WHEN** one source verifies 9 findings, 3 of them with significance 4 or higher
- **THEN** those 3 are kept and the other 6 are recorded as `source_cap`

### Requirement: Catalog format

The catalog SHALL group sources under their class. A `classes` map sets each class's default independence, which a source inherits unless it overrides it. A source SHALL need only an id and a URL. Its region defaults to global and its name to its id. `senders` makes it a newsletter, and `web: false` makes it newsletter-only.

#### Scenario: Class defaults

- **WHEN** a `programmes` source declares only id and URL and the class default is high independence
- **THEN** the source has high independence, region global

#### Scenario: Class without defaults

- **WHEN** a source's class has no defaults and the source declares no independence
- **THEN** reading the catalog fails
