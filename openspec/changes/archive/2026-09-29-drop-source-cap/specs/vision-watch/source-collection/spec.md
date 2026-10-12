## REMOVED Requirements

### Requirement: Per-source volume cap

**Reason**: It discarded already-judged evidence (447 verified findings over W26–W39, against 556 kept) without saving model cost, and capped multi-source channels (inbox, sweep) as if each were one source. The pre-verdict pick of 8 bounds cost; the class cap bounds the AI-news skew; the digest bounds its own size.
**Migration**: None. Past weeks keep their pools unless replayed.

## MODIFIED Requirements

### Requirement: Class volume cap

A catalog class MAY set a weekly cap. The verified findings of that class's sources together SHALL keep at most that many per week, ranked by significance, then recency. The overflow SHALL be recorded as rejected `source_cap`, with a detail naming the class cap. A class without a cap is not limited as a class.

#### Scenario: Busy week for AI newsletters

- **WHEN** `ai-news` has a weekly cap of 6 and its sources verify 11 findings
- **THEN** the 6 strongest are kept and the other 5 are recorded as `source_cap` with a class-cap detail

#### Scenario: Uncapped class

- **WHEN** `press` sets no weekly cap and one press source verifies 9 findings
- **THEN** all 9 are kept
