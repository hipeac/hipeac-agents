# Tasks

## 1. Longer, cited bottom line

- [x] 1.1 `prompts.py`: `BOTTOM_LINE` fragment (3-4 sentences, the 2-3 open questions that moved most and which way, 1-2 `[phrase](F<n>)` citations each, one paragraph), embedded in `DIGEST_STORIES`; `models.py`: `WeeklyDigest.this_week` description to match; verify that a test asserts both prompts carry the fragment
- [x] 1.2 `compose_digest_markdown`: collapse newlines in the bottom line to one paragraph; tests "Bottom line links its evidence" (`F<n>` resolves to the finding URL), "Invented link" in the bottom line (words kept, link dropped), "Bottom line without evidence" (printed); verify `./run pytest tests/agents/vision_watch/test_nodes.py` passes

## 2. Intro-only rewrite

- [x] 2.1 `replace_bottom_line(markdown, paragraph)`: swap the single line after the title and blank line, raise on an unexpected layout; tests show every other line is unchanged byte for byte, newlines in the paragraph are collapsed, and a malformed digest raises
- [x] 2.2 `workspace.rewrite_weekly_digest(week, markdown)`: back up to `_backup/<week>-<timestamp>/digests/weekly/`, overwrite, leave the sent marker; tests in `test_workspace.py` for the backup contents, the new contents and the untouched sent marker
- [x] 2.3 `WeeklyIntro` model and `DIGEST_INTRO` prompt (shared fragment, printed body without the old bottom line); `intro_node`: rebuild material, one call, resolve citations, splice, rewrite; quiet week logs and makes no call; tests with the fake LLM for "Past week rewritten" (ledger and signals files unchanged) and "Quiet week" (no call, file unchanged)
- [x] 2.4 `graph.py`: register `"intro"` on the thinking model; verify through a graph-build test that it gets `models.thinking`
- [x] 2.5 `cli.py`: `--intro-only` for `weekly-digest` only, running `["intro"]`; `parser.error` with `--send` or `--redo`; exit 2 with "no digest for <week>; run weekly-digest first" before building the graph; tests "Combined with send", "No digest yet" (no LLM call) in `tests/test_cli.py`

## 3. Docs and rollout

- [x] 3.1 README: document `--intro-only` next to `--redo`; `ruff format` + `ruff check hipeac_agents` clean; full `./run pytest` passes
- [x] 3.2 Run `--intro-only` on one recorded week (W39) against the live workspace, show the before/after bottom line to the user for review before running on the other weeks
- [x] 3.3 After approval, run it for the other recorded weeks with stories (W26–W38); verify each has a backup and that `git diff --no-index` against the backup touches only line 3
