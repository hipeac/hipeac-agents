# Tasks

## 1. Prose material marks editor tips

- [x] 1.1 In `story_material` (`nodes/digest/node.py`), render a `board-tip` entry's source as `board tip, flagged by an editor`; verify with a digest test that asserts the label on the tip's finding line and its absence on other lines
- [x] 1.2 Add one line to `DIGEST_STORIES` (`nodes/digest/prompts.py`): an editor's tip is a lead the board asked about, so cite it when it bears on the story it sits in; verify with a test that the prose prompt contains the line

## 2. "Board tips" points to where a tip is cited

- [x] 2.1 In `compose_digest_markdown`, after the theme sections, map each tip's finding id to the headings of the themes whose printed items cite it (from the ledger entries' `finding_ids`), and append `· in <heading>[, <heading>]` to that tip's line; verify with tests for a cited tip, a tip clustered but not cited, and an unclustered tip
- [x] 2.2 Check that `weekly-digest --edit` still accepts an unchanged digest whose tip line carries a pointer, and still refuses one where the pointer was altered; verify with the existing edit tests plus one case with a pointer

## 3. Integration

- [x] 3.1 `./run pytest tests -q`, `./run ruff format`, `./run ruff check hipeac_agents` all clean
- [x] 3.2 On a copy of the workspace, `weekly-digest --redo` for W41 (after the tip was re-gated with the page-reading fix): the AI-for-science maths story cites the Erdős tip, and its "Board tips" line ends with "· in AI for science"
