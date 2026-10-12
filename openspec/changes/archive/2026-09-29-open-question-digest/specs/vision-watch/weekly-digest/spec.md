## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Theme sections

Each theme with items SHALL have a heading (its title, or its id) in config order, followed by at most 2 full stories (a short bold title, 1-2 sentences with the evidence cited inline, and the question tag) and then, under "Also moving", its other items as one line each with the tag. An item sits under the theme of its candidate cluster, whichever question it answers. The prose call marks which items are full stories; the limit of 2 is enforced when the digest is assembled, and a full story over the limit is printed as a short item. Texts SHALL not add contrasts ("rather than …", "does not establish …") unless the limit is the finding itself.

#### Scenario: Theme with no entries

- **WHEN** a theme has no story this week
- **THEN** it has no section and is named once in "Quiet this week: …"

#### Scenario: Three stories offered

- **WHEN** the prose call returns three full stories for one theme
- **THEN** the first two are printed as stories and the third as a line under "Also moving"

### Requirement: Digest layout

The digest SHALL contain, in order: a title "HiPEAC Vision Watch — Week <week>: <headline>" (headline at most 8 words); a 1-2 sentence bottom line naming the open question that moved most this week and which way; the theme sections; "Board tips", when any; "Newly converged", when any; one line naming the quiet themes; and a closing line with the number of stories, of short items and of the week's findings, naming the signals log.

#### Scenario: A normal week

- **WHEN** three themes have stories, one of them a new topic, and one board tip was verified
- **THEN** the digest shows the bottom line, three theme sections with each story's tag, the tip, the quiet themes in one line and the closing count

### Requirement: Prose call weighs the evidence itself

The prose call SHALL NOT be given the gate's significance scores. It SHALL be given every open question with its id, and each candidate story with a story key, its evidence status and its findings. It SHALL be asked to weigh a development by what it changes for the answers, not by the size of the company or the money involved.

#### Scenario: No scores in the material

- **WHEN** the week's candidate stories are rendered for the prose call
- **THEN** no finding line carries a significance score; each story line carries its key and status; source and horizon are still shown

#### Scenario: Big spend, small change

- **WHEN** a lab's multi-billion compute deal and an open model closing the gap to frontier models are both candidates
- **THEN** the prose call is instructed to judge them by what they change for the answers, not by the sums involved
