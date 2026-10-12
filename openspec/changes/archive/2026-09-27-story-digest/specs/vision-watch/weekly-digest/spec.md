## RENAMED Requirements

- FROM: `### Requirement: Lead development`
- TO: `### Requirement: Story selection`

## MODIFIED Requirements

### Requirement: Story selection

For each theme, the candidate stories SHALL be the theme's clusters with entries this week, ranked by the highest significance among this week's entries, then novelty, then entries this week, then candidate-trend status, then momentum, then independence, and cut to 4. Each candidate is offered with its 4 most significant new findings. A week with no candidate anywhere SHALL be composed as a quiet week without any prose call.

#### Scenario: Consequential beats solid

- **WHEN** one cluster has three significance-3 entries this week and another has one significance-5 entry
- **THEN** the second is offered first

#### Scenario: Nothing moved

- **WHEN** no cluster received entries this week
- **THEN** the digest is titled "Quiet week" and no prose call is made

### Requirement: Theme sections

Each theme with stories SHALL have a heading (its title, or its id) in config order, followed by at most 2 stories: a short bold title and 2-3 sentences with the evidence cited inline. The limit is enforced when the digest is assembled, whatever the prose call returns; stories on unknown themes are dropped.

#### Scenario: Theme with no entries

- **WHEN** a theme has no story this week
- **THEN** it has no section and is named once in "Quiet this week: …"

#### Scenario: Three stories offered

- **WHEN** the prose call returns three stories for one theme
- **THEN** only the first two are printed

### Requirement: Board tips shown verbatim

Every board-tip finding of the week SHALL be listed under "Board tips" with its summary and link, even when grouping placed it in no cluster.

#### Scenario: Unclustered tip

- **WHEN** a board-tip finding joined no cluster
- **THEN** it still appears under "Board tips"

### Requirement: Sending to the board

With `--send`, and with mail, sending inbox and board address configured, the digest SHALL be emailed to the board address as markdown text plus an HTML part. The subject is the digest's title, "HiPEAC Vision Watch — Week <week>: <headline>", and replies go to the configured reply-to. Each week's digest SHALL be sent at most once. A digest composed without `--send` SHALL be sendable later by running with `--send`.

#### Scenario: Compose, review, then send

- **WHEN** the operator composes a week's digest without `--send`, reviews it, then runs `weekly-digest --send` for that week
- **THEN** the recorded digest is emailed to the board, unchanged, with its title as subject

#### Scenario: Already sent

- **WHEN** `weekly-digest --send` runs for a week whose digest was already sent
- **THEN** nothing is sent again

## REMOVED Requirements

### Requirement: Digest sections

**Reason**: Replaced by "Digest layout": the digest tells stories per theme instead of listing every entry.
**Migration**: None; past digests stay as written.

### Requirement: Lead presentation

**Reason**: The separate lead story repeated a theme story; the bottom line points to the week's most important development instead.
**Migration**: None.

### Requirement: Weak signals

**Reason**: Off-theme rejects are now triaged against the themes; grouping them added length, not signal.
**Migration**: None; rejects stay in the week's audit file.

### Requirement: What's brewing

**Reason**: Long-horizon findings are told inside their theme's stories; a separate list lengthened the digest.
**Migration**: None; every finding is in the signals log.

## ADDED Requirements

### Requirement: Digest layout

The digest SHALL contain, in order: a title "HiPEAC Vision Watch — Week <week>: <headline>" (headline at most 8 words); a 2-3 sentence bottom line naming the week's most important development; the theme sections; "Board tips", when any; "Newly converged", when any; one line naming the quiet themes; and a closing line with the number of stories and of the week's signals, naming the signals log.

#### Scenario: A normal week

- **WHEN** three themes have stories and one board tip was verified
- **THEN** the digest shows the bottom line, three theme sections, the tip, the quiet themes in one line and the closing count

### Requirement: Links only to findings

The prose call SHALL cite findings only by id. Only citations of findings it was given SHALL become links. An unknown id, or any link to a URL it was not given, keeps its words without a link. A bare citation becomes a link on the source's domain. A story that cites no finding SHALL be dropped.

#### Scenario: Invented link

- **WHEN** a story contains a markdown link to a URL that is not one of the week's findings
- **THEN** the words stay and the link is removed

#### Scenario: Story without evidence

- **WHEN** a story cites no finding
- **THEN** it is not printed

### Requirement: Newly converged

A cluster that crosses the candidate-trend threshold with this week's entries SHALL be listed once, that week, under "Newly converged" with its theme and tally, as a candidate to name in the Vision.

#### Scenario: Crossing this week

- **WHEN** a cluster meets the threshold now and did not with last week's entries
- **THEN** it is listed under "Newly converged"; a cluster that had already converged is not

### Requirement: Signals log

Every finding of the week SHALL be written to `digests/weekly/digest-<week>-signals.md`, by theme and story, with findings in no story listed last. The log is not emailed and may be rewritten.

#### Scenario: Finding in no story

- **WHEN** a finding joined no cluster
- **THEN** it is listed under "Not in any story" in the signals log
