# clustering Specification

## Purpose

How weekly findings are grouped into long-running development clusters per theme, so the board can see a story build across weeks and know when it has enough evidence to name in the Vision.

## Requirements

### Requirement: One grouping decision per week

Each week's findings SHALL be grouped by one judgement that sees every existing cluster across all themes and every finding of the week, so one development keeps one cluster identity. The decision SHALL be recorded in `evidence/<week>/grouping.json` and reused on rerun.

#### Scenario: Digest rerun

- **WHEN** `weekly-digest` runs again for a week that has a recorded grouping
- **THEN** the recorded grouping is reused and no new grouping judgement is made

### Requirement: Cluster identity

A finding SHALL extend an existing cluster by default. A new cluster SHALL be opened only when no existing one covers the finding. Cluster ids SHALL name the ongoing development generically (for example `ai-agent-security`), never a single company or announcement. A new cluster lives in the theme the grouping assigns, or the finding's first theme when that theme is unknown.

#### Scenario: New development

- **WHEN** a finding matches no existing cluster
- **THEN** a new cluster is opened, marked as opened that week, with the finding as its first entry

### Requirement: Append-only cluster logs

Each theme SHALL have one cluster log, `clusters/<theme>-clusters.json`, spanning all weeks. Clusters and entries SHALL only ever be added (except by an operator `--redo`). An entry records the week, finding id, source and source class, region, date, title, the finding's summary and URL, and its significance and horizon. Tallies and status SHALL be derived when read, never stored.

#### Scenario: Same finding recorded twice

- **WHEN** a rerun appends a finding already in the cluster
- **THEN** nothing is added and the run continues

### Requirement: Stale entries after a redo

When a week's evidence is redone, the cluster logs SHALL end up describing the week's current findings only. No entry may point at a finding id that now refers to a different finding. A harvest SHALL refuse to run, before spending anything, while the week still has cluster entries from an earlier harvest, and SHALL name `--redo` as the way forward.

#### Scenario: Week harvested again

- **WHEN** a week's evidence is replaced with `--redo` and its digest recomposed
- **THEN** every cluster entry for that week carries the title of the finding its id refers to

#### Scenario: Re-harvest without redo

- **WHEN** a harvest runs for a week whose evidence was moved away by hand but whose cluster entries remain
- **THEN** it stops with a message pointing to `--redo`, without scraping or judging anything

### Requirement: Every finding accounted for

Every finding of the week SHALL either join a cluster or be reported in the run notes as joining none.

#### Scenario: Grouping names an unknown cluster

- **WHEN** the grouping assigns a finding to a cluster id that does not exist and opens no new cluster
- **THEN** the finding is reported as having joined no cluster

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

### Requirement: Classes as of the current catalog

Every tally that uses source classes (reach, primary source, novelty) SHALL take each entry's class from its source's class in the current catalog. When the source is not in the catalog, the entry SHALL keep its recorded class if the catalog still declares it, and otherwise count as `unlisted`, the one non-primary class of findings from outside the catalog. Recorded entries SHALL NOT be rewritten.

#### Scenario: Source reclassified

- **WHEN** imec moves from `capital` to `research` in the catalog, and a cluster has imec entries recorded as `capital`
- **THEN** the next digest counts those entries as `research`, and the cluster log still records `capital`

#### Scenario: Source removed

- **WHEN** a cluster entry's source is no longer in the catalog
- **THEN** the entry counts under its recorded class if the catalog still declares it, and as `unlisted` otherwise
