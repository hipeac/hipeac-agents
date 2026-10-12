## RENAMED Requirements

- FROM: `### Requirement: Synthesis per active cluster`
- TO: `### Requirement: Synthesis per converged story`

## MODIFIED Requirements

### Requirement: Synthesis per converged story

Each cluster active in the month that has crossed the candidate-trend threshold SHALL get a synthesis, at most 10, strongest first: trend name, evidence summary, why it matters, confidence, likelihood, European stake (GAP, OPPORTUNITY or DEPENDENCY), and a recommendation. The synthesis is given the month's entries and the cluster's share of low-independence sources. No cluster may be rendered as a candidate trend without one.

#### Scenario: Missing synthesis

- **WHEN** a candidate-trend section would be rendered without its synthesis
- **THEN** the run fails rather than writing an incomplete digest

#### Scenario: Not converged

- **WHEN** an active cluster has not crossed the threshold
- **THEN** it gets no synthesis call and one line under "Also accumulating"

### Requirement: Digest sections

The monthly digest SHALL contain:

- **Bottom line**, from the 6 active clusters with the most entries;
- **Candidate trends**: the synthesised converged clusters with "News so far";
- **Also accumulating**: one line per other active cluster with its name, theme, entries this month and tally;
- **Theme health**;
- **Quiet / closed**: clusters with no entries in the month.

#### Scenario: Dormant cluster

- **WHEN** a cluster received no entries during the month
- **THEN** it is listed under "Quiet / closed"
