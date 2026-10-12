## MODIFIED Requirements

### Requirement: Append-only cluster logs

Each theme SHALL have one cluster log, `clusters/<theme>-clusters.json`, spanning all weeks. Clusters and entries SHALL only ever be added (except by an operator `--redo`). An entry records the week, finding id, source and source class, region, date, title, the finding's summary and URL, and its significance, direction and horizon. Tallies and status SHALL be derived when read, never stored.

#### Scenario: Same finding recorded twice

- **WHEN** a rerun appends a finding already in the cluster
- **THEN** nothing is added and the run continues

### Requirement: Candidate-trend threshold

A cluster SHALL be a candidate trend when it has at least 4 findings, from at least 3 source classes, across at least 3 weeks, including at least one primary source (a class other than aggregators or community). Below that it is *emerging*. It is *strengthening* once it also spans 6 or more weeks and 4 or more source classes. Progress SHALL be shown as, for example, "3/4 findings · 1/3 source classes · 2/3 weeks — needs 2 more source classes".

#### Scenario: Threshold met

- **WHEN** a cluster reaches 4 findings from 3 source classes over 3 weeks, one of them from a programme source
- **THEN** its status is candidate-trend and its progress reads "threshold met"

#### Scenario: Only commentary

- **WHEN** a cluster's 4 findings over 3 weeks all come from aggregators and community sources
- **THEN** it stays emerging, and its progress asks for a primary source

### Requirement: Standing ranking

Clusters SHALL be ranked by evidence weight: clusters with a primary source first, then source classes × weeks, then the smaller share of entries from low-independence sources.

#### Scenario: Aggregator-only cluster

- **WHEN** two clusters tie on reach and persistence, and one rests mostly on low-independence sources
- **THEN** the other ranks higher
