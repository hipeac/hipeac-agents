# Design

## Context

`compose_digest_markdown` already runs `this_week` through `resolve_citations` (`nodes/digest/node.py`). The prose call never cites in it because the prompt and field description ask for 1-2 uncited sentences. The digest's shape is fixed: title line, blank line, the bottom line as one paragraph, blank line, then sections. `digest_node` rebuilds the prose call's material from the cluster logs scoped through the week (`_collect_clusters`, `story_candidates`, `story_material`). The same code on the same logs gives the same story keys and `F<n>` ids, so a later call can cite ids that resolve to the URLs the digest printed. A recorded digest makes `digest_node` return early. `purge_week` is the existing backup pattern (`_backup/<week>-<timestamp>/`).

## Goals / Non-Goals

**Goals:**

- One bottom-line instruction, used by both the full digest call and the intro-only call.
- The intro-only pass changes one paragraph of one file and nothing else in the workspace except the backup.

**Non-Goals:**

- Anchor links from the bottom line to sections. Mail clients handle in-page anchors poorly, and the board asked for sources.
- A batch option across weeks. The operator runs one command per week.
- Re-mailing rewritten digests.

## Decisions

### Intro node beside the digest node

Add `intro_node` to `nodes/digest/node.py`, registered in `graph.py` as `"intro"` on the thinking model. The CLI runs `["intro"]` for `--intro-only`, without `cluster`. The node reuses the material builders and `resolve_citations` directly, and it gets no services, because it neither sends nor reads Vision.

The alternative was a plain function called from the CLI. It was rejected because it would bypass the model tiers, the usage printout and the graph's service boundary, which every other LLM run goes through.

### Shared bottom-line instruction

`prompts.py` gets a `BOTTOM_LINE` fragment (3-4 sentences, the 2-3 questions that moved most, 1-2 citations per question, plain words, one paragraph). `DIGEST_STORIES` embeds it for `this_week`. `DIGEST_INTRO` embeds it too, plus the house-style citation rule, and tells the model that the printed digest follows so the bottom line agrees with it. `models.py` gets `WeeklyIntro(this_week: str)` for the intro call's structured output. `WeeklyDigest.this_week`'s description changes to match.

### The prose call sees both material and printed body

The rebuilt material provides the `F<n>` ids to cite. The printed body (everything after the old bottom line) shows which stories the board actually got, so the bottom line doesn't lead with a candidate the original call skipped. The old bottom line is left out of the input so the model doesn't paraphrase it.

### Splice by position, in code

`replace_bottom_line(markdown, paragraph)` is a pure function. It checks the layout (a title line starting with `# `, a blank line, one non-empty line, a blank line) and swaps that one non-empty line. Newlines in the model's output are collapsed to spaces first, so the new bottom line stays a single line. A digest that doesn't match the layout raises instead of guessing, because the layout is what makes the swap safe. The full composition path also collapses newlines, so later digests keep this layout.

### Workspace write

`rewrite_weekly_digest(week, markdown)` in `workspace.py` copies the current file to `_backup/<week>-<timestamp>/digests/weekly/`, then overwrites it. It is the documented exception to `write_once`, next to `purge_week`, and it never touches the sent marker.

### CLI guards

`--intro-only` is accepted only with `weekly-digest`. Combined with `--send` or `--redo` it is a `parser.error`, raised before anything else runs. A missing digest prints `no digest for <week>; run weekly-digest first` and exits 2, before the graph is built. The node handles a quiet week (empty `material.refs`) by logging and returning without a call.

## Risks / Trade-offs

- [`themes.yaml` or the source catalog changed since the week ran, so the rebuilt candidates differ] → The link guard means a stale id loses its link and never points at the wrong URL. The printed body keeps the bottom line on the stories that were printed.
- [The mailed copy and the workspace copy differ] → Accepted. The backup keeps the mailed text. Run summaries note that nothing was sent.
- [The model still writes 1-2 sentences or cites nothing] → The prompt asks for citations and the spec allows an uncited bottom line. The operator reviews it and can rerun, which is cheap.

## Migration Plan

After this lands, for each recorded week W26–W39 with stories: `./run weekly-digest --on <date in week> --intro-only`, then review the diffs against `_backup/`. To roll back, restore the backed-up file. New weeks get the longer bottom line on normal composition.
