## MODIFIED Requirements

### Requirement: Theme sections

"What moved in each theme" SHALL have one heading per theme id, in config order. Each lists this week's entries of that theme's clusters, most significant first and then most recent, up to 12, with a "+N more entries" note beyond that. Each entry is tagged with its direction when known.

#### Scenario: Theme with no entries

- **WHEN** no cluster of a theme received entries this week
- **THEN** that theme's section reads "Quiet week — no entries this window."

### Requirement: Lead development

The lead SHALL be the cluster emerging most this week. Ranking is by the highest significance among this week's entries, then novelty, then entries this week, then candidate-trend status, then momentum, then independence. Novelty is 1 for a cluster first seen this week; otherwise one point per source class and per region reached for the first time.

#### Scenario: Consequential beats solid

- **WHEN** one cluster has three significance-3 entries this week and another has one significance-5 entry
- **THEN** the second leads

#### Scenario: Nothing moved

- **WHEN** no cluster received entries this week
- **THEN** the digest has no "One big thing" section
