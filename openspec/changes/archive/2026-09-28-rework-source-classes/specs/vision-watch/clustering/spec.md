## MODIFIED Requirements

### Requirement: Candidate-trend threshold

A cluster SHALL be a candidate trend when it has at least 4 findings, from at least 3 source classes, across at least 3 weeks, including at least one primary source (a source whose class is primary in the catalog). Findings from outside the catalog (sweep, inbox, board tips) SHALL count as one non-primary class. Below the threshold a cluster is *emerging*. It is *strengthening* once it also spans 6 or more weeks and 4 or more source classes.

#### Scenario: Threshold met

- **WHEN** a cluster reaches 4 findings from 3 source classes over 3 weeks, one of them from a programme source
- **THEN** its status is candidate-trend

#### Scenario: Only commentary

- **WHEN** a cluster's 4 findings over 3 weeks all come from press, ai-news and commentary sources
- **THEN** it stays emerging

### Requirement: Standing ranking

Clusters SHALL be ranked by evidence weight: clusters with a primary source first, then source classes × weeks.

#### Scenario: Aggregator-only cluster

- **WHEN** two clusters tie on reach and persistence, and only one has a primary source
- **THEN** the one with the primary source ranks higher

## ADDED Requirements

### Requirement: Classes as of the current catalog

Every tally that uses source classes (reach, primary source, novelty) SHALL take each entry's class from its source's class in the current catalog. When the source is not in the catalog, the entry SHALL keep its recorded class if the catalog still declares it, and otherwise count as `unlisted`, the one non-primary class of findings from outside the catalog. Recorded entries SHALL NOT be rewritten.

#### Scenario: Source reclassified

- **WHEN** imec moves from `capital` to `research` in the catalog, and a cluster has imec entries recorded as `capital`
- **THEN** the next digest counts those entries as `research`, and the cluster log still records `capital`

#### Scenario: Source removed

- **WHEN** a cluster entry's source is no longer in the catalog
- **THEN** the entry counts under its recorded class if the catalog still declares it, and as `unlisted` otherwise
