## MODIFIED Requirements

### Requirement: Story selection

For each theme, the candidate stories SHALL be the theme's clusters with entries this week, ranked by the highest significance among this week's entries, then novelty, then entries this week, then candidate-trend status, then momentum, and cut to 4. Each candidate is offered with its 4 most significant new findings. A week with no candidate anywhere SHALL be composed as a quiet week without any prose call.

#### Scenario: Consequential beats solid

- **WHEN** one cluster has three significance-3 entries this week and another has one significance-5 entry
- **THEN** the second is offered first

#### Scenario: Nothing moved

- **WHEN** no cluster received entries this week
- **THEN** the digest is titled "Quiet week" and no prose call is made
