## MODIFIED Requirements

### Requirement: Synthesis per converged story

Each cluster active in the month that has crossed the candidate-trend threshold SHALL get a synthesis, at most 10, strongest first: trend name, evidence summary, why it matters, confidence, likelihood, European stake (GAP, OPPORTUNITY or DEPENDENCY), and a recommendation. The synthesis is given the month's entries and the cluster's share of entries from European sources (region `eu`). No cluster may be rendered as a candidate trend without one.

#### Scenario: Missing synthesis

- **WHEN** a candidate-trend section would be rendered without its synthesis
- **THEN** the run fails rather than writing an incomplete digest

#### Scenario: Not converged

- **WHEN** an active cluster has not crossed the threshold
- **THEN** it gets no synthesis call and one line under "Also accumulating"

#### Scenario: Europe agreeing with itself

- **WHEN** 5 of a converged cluster's 6 entries come from region `eu` sources
- **THEN** the synthesis is told the European share is 83%
