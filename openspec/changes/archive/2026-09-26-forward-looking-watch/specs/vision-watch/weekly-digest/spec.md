## MODIFIED Requirements

### Requirement: Digest sections

The digest SHALL contain, in order:

- **In brief**: about 100 words, the bottom line of the week's top 5 clusters;
- **One big thing**: the lead cluster (see Lead development);
- **What's brewing**, when any;
- **What moved on each question** (see Theme sections);
- **Board tips this week**, when any;
- **Also worth watching**, when any off-theme rejects form a coherent group;
- **Trending this week**: up to 10 clusters with movement, ranked by evidence weight, each "converged — consider naming it in the Vision" or "still gathering evidence".

#### Scenario: Trending status

- **WHEN** a cluster with movement this week meets the candidate-trend threshold
- **THEN** its trending line reads "converged — consider naming it in the Vision"

### Requirement: Theme sections

"What moved on each question" SHALL have one heading per watch question, in config order, reading "<id> — <question>". Each heading lists this week's entries of that question's clusters, strongest tier first and then most recent, up to 12, with a "+N more entries" note beyond that. Each entry is tagged with its direction when known.

#### Scenario: Theme with no entries

- **WHEN** no cluster of a question received entries this week
- **THEN** that question's section reads "Quiet week — no entries this window."

### Requirement: Lead development

The lead SHALL be the cluster emerging most this week. Ranking is by the highest forward significance among this week's entries, then novelty, then best tier this week, then entries this week, then candidate-trend status, then momentum, then independence. Novelty is 1 for a cluster first seen this week; otherwise one point per source class and per region reached for the first time.

#### Scenario: Consequential beats solid

- **WHEN** one cluster's best entry this week is tier 1 with significance 3 and another's is tier 3 with significance 5
- **THEN** the second leads

#### Scenario: Nothing moved

- **WHEN** no cluster received entries this week
- **THEN** the digest has no "One big thing" section

## ADDED Requirements

### Requirement: What's brewing

The digest SHALL list up to 8 of the week's findings with a 3–5-year horizon or from foresight and community sources, most significant first. Each shows its summary, forward note, source link and horizon.

#### Scenario: Long-horizon finding

- **WHEN** a finding has horizon 3–5y and a forward note
- **THEN** it appears under "What's brewing" with its note and "(3-5y)"
