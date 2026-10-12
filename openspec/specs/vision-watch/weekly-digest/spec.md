# weekly-digest Specification

## Purpose

The weekly digest the editorial board receives: a bottom line on the 2-3 open questions that moved most, linking the findings it cites, then per theme the stories tagged with the open question each moves and which way, the board tips and newly converged stories; a ledger of every printed item and a workspace log of every signal are written beside it, and it is optionally mailed.

## Requirements

### Requirement: Composed from the cluster logs

The digest SHALL be composed from the week's cluster entries, scoped to entries recorded up to and including that week, so a digest recomposed later reports the same tallies.

#### Scenario: Later weeks exist

- **WHEN** the W30 digest is composed after W31 entries were recorded
- **THEN** W31 entries do not count in any W30 tally

### Requirement: Theme sections

Each theme with items SHALL have a heading (its title, or its id) in config order, followed by at most 2 full stories (a short bold title, 1-2 sentences with the evidence cited inline, and the question tag) and then, under "Also moving", its other items as one line each with the tag. An item sits under the theme of its candidate cluster, whichever question it answers. The prose call marks which items are full stories; the limit of 2 is enforced when the digest is assembled, and a full story over the limit is printed as a short item. Texts SHALL not add contrasts ("rather than …", "does not establish …") unless the limit is the finding itself.

#### Scenario: Theme with no entries

- **WHEN** a theme has no story this week
- **THEN** it has no section and is named once in "Quiet this week: …"

#### Scenario: Three stories offered

- **WHEN** the prose call returns three full stories for one theme
- **THEN** the first two are printed as stories and the third as a line under "Also moving"

### Requirement: Stories tagged with the question they move

Every item the prose call writes, full story or short item, SHALL name its candidate by story key and the open question it bears on by id (any theme's, not only its own), or NEW when the development matters but no question covers it, with its lean: the direction it pushes the answer in a few words, never a restatement of the question, or for NEW the topic. Every candidate that bears on a question or matters for the Vision SHALL get an item; a release, a benchmark, a standard, a deployment figure or a rule counts when it bears on a question. When the digest is assembled, an item SHALL be dropped when its question id or story key is unknown, when its story key was already used, or when it cites no finding. Each item SHALL carry its tag: the question's text and "→ <lean>", or "new topic: <lean>".

#### Scenario: Question text instead of id

- **WHEN** the prose call names a story's question by its text rather than its id
- **THEN** the story is not printed and a warning is logged

#### Scenario: Release on the frontier question

- **WHEN** a candidate reports two frontier model releases and a benchmark reproducibility effort
- **THEN** it gets an item tagged with the frontier-gap question, not left out as a product launch

#### Scenario: Story answers another line's question

- **WHEN** a story in the New hardware section shows robot inference running fully onboard
- **THEN** it stays in New hardware and its tag names `physical-ai.2`

### Requirement: Interdisciplinary items, no echoes

A finding joins clusters in every theme it is tagged with, so one development can reach several themes. It MAY appear under several themes when each item answers a different question. When the digest is assembled, in theme order, an item that links only findings already linked by an earlier item on the same question SHALL be dropped. An item repeated under another theme SHALL end its tag with "also in <theme>", naming the theme where it first appeared. This is enforced in code, whatever the prose call returns.

#### Scenario: Same question in two themes

- **WHEN** DeepMind's server-side memory is a full story under Next computing paradigm and a short item under Cybersecurity, both tagged `next-computing-paradigm.2`
- **THEN** it is printed only under Next computing paradigm

#### Scenario: Different question in each theme

- **WHEN** an EDA item is tagged with the chiplet-standards question under New hardware and with "How does the engineer's work change?" under AI-built software and hardware
- **THEN** it is printed in both, the second tag ending with "also in New hardware"

### Requirement: Early signals labelled

A full story whose cluster is emerging (below the candidate-trend threshold) SHALL be labelled "early signal" in its tag. One-line items under "Also moving" SHALL NOT carry the label. The ledger SHALL flag every printed item from an emerging cluster as early, full or one-line. The label and flag SHALL come from the cluster's derived status, not from the prose call.

#### Scenario: One item on a question

- **WHEN** a full story comes from a cluster with one finding in its first week
- **THEN** its tag ends with "early signal"

#### Scenario: Early one-line item

- **WHEN** an "Also moving" item comes from an emerging cluster
- **THEN** its tag has no "early signal" label and its ledger entry is flagged early

### Requirement: Weekly ledger

Composing a weekly digest SHALL write `digests/weekly/digest-<week>-ledger.json` with every printed story: question id and the question's text at that time (or NEW), lean, theme, story (cluster id), evidence status, early-signal flag, cited finding ids, title and text. A week without a prose call has an empty ledger.

#### Scenario: Signal recorded

- **WHEN** the W37 digest prints a story tagged `cybersecurity.3` citing two findings of cluster `agent-sandbox-escapes`
- **THEN** the W37 ledger holds it with the question's text, its lean, the cluster id, the cluster's status and both finding ids

#### Scenario: Quiet week

- **WHEN** no cluster received entries this week
- **THEN** an empty ledger is written beside the quiet-week digest

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

### Requirement: Board tips shown verbatim

Every board-tip finding of the week SHALL be listed under "Board tips" with its summary and link, even when grouping placed it in no cluster. A tip that a printed item cites SHALL be followed by a pointer to the heading of each theme where it is cited.

#### Scenario: Unclustered tip

- **WHEN** a board-tip finding joined no cluster
- **THEN** it still appears under "Board tips", with no pointer

#### Scenario: Tip cited in a story

- **WHEN** a board-tip finding is cited by a printed item under "AI for science"
- **THEN** its line under "Board tips" ends with "· in AI for science"

#### Scenario: Tip clustered but not cited

- **WHEN** a board-tip finding belongs to a candidate story but no printed item cites it
- **THEN** it appears under "Board tips" with no pointer

### Requirement: Write-once digest

The digest SHALL be written once to `digests/weekly/digest-<week>.md`. A week that already has a digest SHALL not be recomposed. The only in-place changes allowed SHALL be an intro-only rewrite of its bottom line and a light edit of its story prose.

#### Scenario: Digest run twice

- **WHEN** `weekly-digest` runs for a week that already has a digest
- **THEN** it prints "already has a digest; skipping composition" and makes no prose calls

### Requirement: Sending to the board

With `--send`, and with mail, sending inbox and board address configured, the digest SHALL be emailed to the board address as markdown text plus an HTML part. The subject is the digest's title, "HiPEAC Vision Watch — Week <week>: <headline>", and replies go to the configured reply-to. Each week's digest SHALL be sent at most once. A digest composed without `--send` SHALL be sendable later by running with `--send`.

#### Scenario: Compose, review, then send

- **WHEN** the operator composes a week's digest without `--send`, reviews it, then runs `weekly-digest --send` for that week
- **THEN** the recorded digest is emailed to the board, unchanged, with its title as subject

#### Scenario: Already sent

- **WHEN** `weekly-digest --send` runs for a week whose digest was already sent
- **THEN** nothing is sent again

### Requirement: Digest layout

The digest SHALL contain, in order: a title "HiPEAC Vision Watch — Week <week>: <headline>" (headline at most 8 words); a bottom line of one paragraph, 3-4 sentences, on the 2-3 open questions that moved most this week and which way, each sentence leading with what changed rather than the question's wording, without hedges, citing 1-2 findings for each; the theme sections; "Board tips", when any; "Newly converged", when any; one line naming the quiet themes; and a closing line with the number of stories, of short items and of the week's findings, naming the signals log.

#### Scenario: A normal week

- **WHEN** three themes have stories, one of them a new topic, and one board tip was verified
- **THEN** the digest shows the bottom line, three theme sections with each story's tag, the tip, the quiet themes in one line and the closing count

#### Scenario: Bottom line links its evidence

- **WHEN** the bottom line says new findings show that parsing can undermine agent oversight, citing that finding
- **THEN** the phrase stating it links to that finding's URL

### Requirement: Links only to findings

The prose call SHALL cite findings only by id, in the stories and in the bottom line. Only citations of findings it was given SHALL become links. An unknown id, or any link to a URL it was not given, keeps its words without a link. A bare citation becomes a link on the source's domain. A story that cites no finding SHALL be dropped. A bottom line that cites no finding SHALL still be printed.

#### Scenario: Invented link

- **WHEN** a story or the bottom line contains a markdown link to a URL that is not one of the week's findings
- **THEN** the words stay and the link is removed

#### Scenario: Story without evidence

- **WHEN** a story cites no finding
- **THEN** it is not printed

#### Scenario: Bottom line without evidence

- **WHEN** the bottom line cites no finding
- **THEN** it is printed without links

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

### Requirement: Prose call weighs the evidence itself

The prose call SHALL NOT be given the gate's significance scores. It SHALL be given every open question with its id, and each candidate story with a story key, its evidence status and its findings. It SHALL be asked to weigh a development by what it changes for the answers, not by the size of the company or the money involved. A board-tip finding SHALL be marked in the material as flagged by an editor, and the prose call SHALL be asked to cite an editor's tip when it bears on the story it sits in.

#### Scenario: No scores in the material

- **WHEN** the week's candidate stories are rendered for the prose call
- **THEN** no finding line carries a significance score; each story line carries its key and status; source and horizon are still shown

#### Scenario: Big spend, small change

- **WHEN** a lab's multi-billion compute deal and an open model closing the gap to frontier models are both candidates
- **THEN** the prose call is instructed to judge them by what they change for the answers, not by the sums involved

#### Scenario: Tip in a candidate story

- **WHEN** a board-tip finding belongs to a candidate story
- **THEN** its finding line says an editor flagged it, and the prose call is instructed to cite it when it bears on that story

### Requirement: Rewriting the bottom line

`weekly-digest --on <date> --intro-only` SHALL rewrite only the bottom line of the week's recorded digest. The prose call SHALL be given the week's candidate stories, rebuilt from the cluster logs as for composition, and the printed digest, and SHALL return only the bottom line, under the same rules and link guard as at composition. Before the digest is changed, it SHALL be copied to `_backup/<week>-<timestamp>/`. The title, sections, closing line, ledger, signals log and sent marker SHALL stay unchanged, and nothing SHALL be emailed. The flag SHALL be refused with `--send` or `--redo`. A week without a digest SHALL fail, naming the command to compose it. A week with no candidate stories SHALL be left unchanged without a prose call.

#### Scenario: Past week rewritten

- **WHEN** the operator runs `weekly-digest --on 2026-09-25 --intro-only` and W39 has a digest
- **THEN** the W39 bottom line is replaced by a cited 3-4 sentence one, the previous digest is in `_backup/2026-W39-<timestamp>/`, and every other line of the digest is unchanged

#### Scenario: Sent week rewritten

- **WHEN** the rewritten week's digest was already sent
- **THEN** its sent marker stays and no email is sent

#### Scenario: Combined with send

- **WHEN** the operator runs `weekly-digest --intro-only --send`
- **THEN** the run exits with a usage error and nothing is changed

#### Scenario: No digest yet

- **WHEN** the operator runs `--intro-only` for a week with no digest
- **THEN** the run fails, naming `weekly-digest` to compose it, and makes no prose call

#### Scenario: Quiet week

- **WHEN** the week has no candidate stories
- **THEN** the digest is left unchanged and no prose call is made

### Requirement: Editing the story prose

`weekly-digest --on <date> --edit` SHALL lightly reword the story prose of the week's recorded digest — the sentences of the full stories and the one-line items under "Also moving" — keeping every fact, item and line. Code SHALL refuse an edit that changes anything else: the title, the bottom line, the headings, the question tags, the board tips, the newly converged list, the quiet line and the closing counts are frozen, and a line whose links are added, dropped or re-pointed is refused, so the ledger and the link guard keep standing behind the digest. Before the digest is changed, it SHALL be copied to `_backup/<week>-<timestamp>/`. The ledger, signals log and sent marker SHALL stay unchanged, and nothing SHALL be emailed. An edit that changes nothing SHALL write nothing. The flag SHALL be refused with `--send`, `--redo` or `--intro-only`. A week without a digest SHALL fail, naming the command to compose it.

#### Scenario: Awkward phrasing reworded

- **WHEN** a recorded story reads "its model handles items without prior knowledge" citing one article, and the edit pass rewords it with the same link
- **THEN** the story prose is replaced, the previous digest is in `_backup/<week>-<timestamp>/`, and every other line is unchanged

#### Scenario: Citation moved

- **WHEN** the edited digest re-points a story's link to a URL that is not the finding it cited
- **THEN** the edit is refused, the recorded digest stays as it was, and no backup is written

#### Scenario: Combined with send

- **WHEN** the operator runs `weekly-digest --edit --send`
- **THEN** the run exits with a usage error and nothing is changed

#### Scenario: No digest yet

- **WHEN** the operator runs `--edit` for a week with no digest
- **THEN** the run fails, naming `weekly-digest` to compose it, and makes no prose call
