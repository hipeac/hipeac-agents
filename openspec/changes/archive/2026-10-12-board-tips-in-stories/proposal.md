# Proposal

## Why

In W41 an editor's tip (the Erdős problems site pausing proof claims because it is flooded with unexplained AI-generated proofs) was grouped into the same story as OpenAI's maths batch. The prose call still wrote "Mathematics increases the checking burden" from the OpenAI item alone. Its material showed the tip as just another finding with `source: board-tip`, nothing marked it as a lead the board itself asked about, and the gate's verdict on it was empty. The gate now reads a tip's page (fixed separately), but the prose call still cannot tell an editor's tip from any other finding. Separately, "Board tips" lists every tip the same way, so a tip that a story did use looks unprocessed.

## What Changes

- In the prose call's material, a board-tip finding is labelled as flagged by an editor. The prompt says an editor's tip is a lead the board asked about, and that the call should cite it when it bears on the story. It stays a judgement call: a tip that bears on nothing is still not forced into a story.
- "Board tips" still lists every tip of the week. A tip that a printed item cites gets a pointer to the theme heading(s) where it appears, e.g. `— [terrytao.wordpress.com](…) · in AI for science`.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/weekly-digest`: The prose-call material marks board tips (*Prose call weighs the evidence itself*). The "Board tips" list points to where a cited tip appears (*Board tips shown verbatim*).

## Impact

- **Code:** `nodes/digest/node.py` (`story_material` labels board-tip entries; `compose_digest_markdown` adds the pointer), `nodes/digest/prompts.py` (`DIGEST_STORIES`: one line on editor tips), and the digest tests.
- **Workspace:** none. Recorded digests are write-once and stay as they are. `--edit` already freezes the "Board tips" lines, pointer included.
