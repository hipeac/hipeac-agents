## MODIFIED Requirements

### Requirement: Digest sections

The digest SHALL contain, in order:

- **In brief**: about 100 words, the bottom line of the week's top 5 clusters;
- **One big thing**: the lead cluster (see Lead development);
- **What's brewing**, when any;
- **What moved in each theme** (see Theme sections);
- **Board tips this week**, when any;
- **Also worth watching**, when any off-theme rejects form a coherent group;
- **Trending this week**: up to 10 clusters with movement, ranked by evidence weight, each "converged — consider naming it in the Vision" or "still gathering evidence".

#### Scenario: Trending status

- **WHEN** a cluster with movement this week meets the candidate-trend threshold
- **THEN** its trending line reads "converged — consider naming it in the Vision"

### Requirement: Theme sections

"What moved in each theme" SHALL have one heading per theme id, in config order. Each lists this week's entries of that theme's clusters, strongest tier first and then most recent, up to 12, with a "+N more entries" note beyond that. Each entry is tagged with its direction when known.

#### Scenario: Theme with no entries

- **WHEN** no cluster of a theme received entries this week
- **THEN** that theme's section reads "Quiet week — no entries this window."
