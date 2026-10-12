## MODIFIED Requirements

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
