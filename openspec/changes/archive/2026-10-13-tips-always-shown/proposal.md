# Proposal

## Why

The prose call sees at most 4 findings per candidate story, ranked by gate significance. Board tips usually score low, so in a story with 5 or more new findings this week the tip is cut before the prose call sees it, and the instruction to cite an editor's tip never applies. W41 escaped only because its maths story had 2 new findings.

## What Changes

- A candidate story's board-tip findings are always among the findings shown to the prose call, ahead of the significance ranking; the cap per story is unchanged.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/weekly-digest`: *Prose call weighs the evidence itself* — board tips are never cut from a story's findings.

## Impact

- **Code:** `nodes/digest/node.py` (`story_material` ordering), digest tests.
- **Workspace:** none.
