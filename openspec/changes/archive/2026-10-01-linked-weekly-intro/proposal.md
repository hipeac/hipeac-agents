# Proposal

## Why

The editorial board reads the bottom line at the top of the weekly digest first. Today it has no links, so a claim like "new findings show that parsing can undermine oversight" can't be traced to a source without searching the sections below. The board asked for links there, and a 1-2 sentence line on a single question is too thin to work as the week's overview. The W26–W39 digests already written should get the new intro without being recomposed, which would change their stories and cost a full prose call per week.

## What Changes

- The bottom line becomes 3-4 sentences on the 2-3 open questions that moved most this week, and which way. It cites 1-2 findings per question inline, `[phrase](F<n>)`, the same way items do, so the phrase links to the source.
- Citations in the bottom line go through the same link guard as items: only this week's findings become links, and anything else keeps its words but loses the link. A bottom line that cites nothing is still printed.
- New `weekly-digest --on <date> --intro-only` rewrites only the bottom line of a digest that is already recorded:
  - It rebuilds the week's candidate stories from the cluster logs, then makes one prose call that sees them and the printed digest and returns only the bottom line.
  - The previous digest is backed up to `_backup/<week>-<timestamp>/`. The title, sections, ledger, signals log and sent marker stay as they are.
  - It refuses `--send` and `--redo`, and fails when the week has no digest. A quiet week is left untouched without a prose call.
- The write-once rule gets one exception: an intro-only rewrite of the bottom line.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/weekly-digest`: Digest layout (longer, cited bottom line); Links only to findings (covers the bottom line); Write-once digest (intro-only exception); new requirement Rewriting the bottom line.

## Impact

- **Code:** `nodes/digest/prompts.py` (bottom-line instruction shared by the full and intro-only calls), `nodes/digest/models.py` (`this_week` description, intro-only output model), `nodes/digest/node.py` (intro node, splicing the bottom line), `graph.py` (register the node on the thinking model), `workspace.py` (backed-up intro rewrite), `cli.py` (`--intro-only` flag and its refusals), README.
- **Tests:** a bottom-line citation resolves, an invented link in it is stripped, the splice keeps everything else byte for byte, the backup is written, the sent marker is untouched, and the refusals and quiet-week skip work.
- **Operations:** one thinking-model call per past week, run once for each recorded week with stories. Copies already mailed to the board keep their old intro. Only the workspace copy changes.
- **Out of scope:** the monthly digest's lead.
