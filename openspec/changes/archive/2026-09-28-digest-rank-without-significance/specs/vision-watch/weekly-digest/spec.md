## MODIFIED Requirements

### Requirement: Story selection

For each theme, the candidate stories SHALL be the theme's clusters with entries this week, ranked by novelty, then the number of source classes among this week's entries, then entries this week, then candidate-trend status, then momentum, and cut to 4. The significance the gate gave a finding SHALL NOT rank stories. Each candidate is offered with its 4 most significant new findings. A week with no candidate anywhere SHALL be composed as a quiet week without any prose call.

#### Scenario: Consequential beats solid

- **WHEN** one established cluster reaches two source classes new to it this week, and another established cluster gets one significance-5 entry from a class it already had
- **THEN** the first is offered first

#### Scenario: Broad beats loud

- **WHEN** two clusters tie on novelty, one with three entries this week from three source classes and one with a single significance-5 entry
- **THEN** the first is offered first

#### Scenario: Nothing moved

- **WHEN** no cluster received entries this week
- **THEN** the digest is titled "Quiet week" and no prose call is made

## ADDED Requirements

### Requirement: Prose call weighs the evidence itself

The prose call SHALL NOT be given the gate's significance scores. It SHALL be asked to weigh a development, for the stories and for the bottom line, by what it changes for the theme's open questions, not by the size of the company or the money involved.

#### Scenario: No scores in the material

- **WHEN** the week's candidate stories are rendered for the prose call
- **THEN** no finding line carries a significance score; source and horizon are still shown

#### Scenario: Big spend, small change

- **WHEN** a lab's multi-billion compute deal and an open model closing the gap to frontier models are both candidates
- **THEN** the prose call is instructed to judge them by the Vision's open questions, not by the sums involved
