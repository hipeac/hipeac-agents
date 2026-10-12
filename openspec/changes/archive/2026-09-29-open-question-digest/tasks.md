# Tasks

## 1. Questions and ledger model

- [x] 1.1 Add question ids to `ThemeDef` (a `question_ids()` or `questions_by_id` view, `<theme>.<n>` from 1) and a ledger file schema in `schemas.py`, with `workspace` write/read of `digests/weekly/digest-<week>-ledger.json`; test the ids ("Question ids") and a ledger round trip; verify `./run pytest tests/agents/vision_watch/test_schemas.py tests/agents/vision_watch/test_workspace.py` passes

## 2. Weekly digest

- [x] 2.1 Key the stories in `story_material` (S1… beside the status) and add the open-questions block (id, line, text) to the prompt input; replace `StoryDigest` with the signals model; rewrite `DIGEST_STORIES` from prototype v5 (`~/.cache/vw/proto5.py`: question ids, directional lean, NEW, full vs short items, releases and benchmarks count, no contrasts, weigh by the answers); test the material carries keys, statuses and question ids and no significance
- [x] 2.2 Assemble by theme with question tags: drop items with unknown question id, unknown or repeated story key, or no citation; place each under its cluster's theme; at most 2 full stories, the rest under "Also moving"; drop items that repeat the same findings on the same question, mark kept repeats "also in <theme>"; print the tag (question text → lean, or new topic) with the early-signal label from the derived status; test "Question text instead of id", "Story answers another line's question", "Same question in two themes", "Different question in each theme", "One item on a question", "A normal week", "Three stories offered"
- [x] 2.3 Write the ledger with the digest (empty on a quiet week); test "Signal recorded" and "Quiet week"; verify the digest tests pass
- [x] 2.4 Print "early signal" on full stories only, not on "Also moving" items (the ledger still flags both); test "Early one-line item"

## 3. Monthly digest

- [x] 3.1 Read the month's ledgers and compute the gate in plain code (after an A/B on July-September: three signals across two weeks; new topics three signals, two once converged): qualifying questions, qualifying NEW topics by cluster, thin evidence, no evidence, earlier questions (text mismatch); test "One early signal" and "Question reworded"
- [x] 3.2 Replace the syntheses with one call (models with the id restricted to the qualifying ids, prompt in `nodes/monthly/`), drop unqualified answers, counts from code, and the new sections with questions across themes ordered by signals then weeks; no call when nothing qualifies; test "Answer for an unqualified question", "Nothing qualifies" and the ordering; verify the monthly tests pass

- [x] 3.3 Fix `month_weeks` taking the next month's first Friday (September took W40); regression test

## 4. Docs

- [x] 4.1 Update README (what the digests contain) and the `openspec/config.yaml` glossary (question id, ledger); verify the full suite and `ruff format` / `ruff check hipeac_agents` are clean

## 5. Check

- [x] 5.1 On a scratch copy, recompose W26–W39 and compose September's monthly digest; compare with prototype v3 (signals per week, early labels, gate choices, unanswered questions) and report token usage (prototype v3 was gone from `/tmp`; compared against the previous layout and the first monthly runs instead; W26–W39 and July–September then installed in the live workspace)
