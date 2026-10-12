# Proposal

## Why

The board is writing the HiPEAC Vision 2027 anew, around the lines and open questions in `themes.yaml`. The digests don't help with that. The weekly digest retells the week's news by theme; the monthly digest synthesises clusters and gives each a generic recommendation. Neither says which open question a development bears on, or which way it pushes the answer. The result reads as a curated news collection.

A prototype on W35–W39 (2026-09-28, `/tmp/vw/proto3.py`) tied each weekly signal to an open question with its "lean", the direction the evidence pushes the answer. It then built a monthly view per question: where the answer stands, the evidence across weeks, a draft position for 2027, and what is still missing. That output is directly usable for writing:

- **Agent safety.** "How are agents kept safe from prompt injection and misuse?" → independent containment and oversight are essential (4 signals, 3 weeks). Draft position: require independently enforced isolation, constrained publishing and communication, and audit trails that agents cannot alter.
- **Europe's dependencies.** "Are Europe's dependencies growing or shrinking?" → alternatives emerge; dependency reduction is unproven (4 signals, 4 weeks). Draft position: distinguish infrastructure located in Europe from infrastructure Europe controls.
- **Blind spots.** Fifteen of the 30 questions got no evidence in the month, including the frontier-vs-open gap and all of Local AI. That tells the board where the watch is blind.

The prototype also showed what the model can't be trusted with. It returns question text where ids are needed, and it overstates thin evidence. So ids, evidence status, thresholds and the list of unanswered questions are decided in code.

## What Changes

- **Question ids.** Each theme question gets a positional id, `<theme>.<n>` (e.g. `agentic-ai.1`).
- **Weekly digest: theme sections stay**, since board members follow their own lines week to week.
  - Each story carries a tag with the question it moves, from any line, and its lean ("→ onboard inference gaining ground"), or "new topic: …" when no question covers it.
  - A story from an emerging cluster is labelled an early signal.
  - Two tiers per theme: at most 2 full stories, then every other candidate as one line under "Also moving", each with its tag. The cap keeps each theme short; the second tier keeps every question that moved visible. Tested on W39 and W37 (v5): all 25 and 22 candidates used, only Continuum infrastructure quiet, the frontier-gap question answered for the first time; without the second tier the model dropped 13 of 25 (v4).
  - Code checks question ids and story keys, requires cited evidence, keeps interdisciplinary items that answer a different question in each theme (6 of 7 repeats in W39/W37) while dropping echoes on the same question, marking repeats "also in <theme>" and enforces the tiers.
  - Unchanged: candidate selection per theme, citations by finding id, board tips, "Newly converged", quiet themes and the signals log.
- **Ledger.** Each weekly digest writes a ledger of its signals (question id and text, lean, story, status, findings, text).
- **BREAKING (monthly digest).** The monthly digest becomes "where the open questions stand", across themes rather than by theme. It has a bottom line; per question with enough evidence, most evidence first and tagged with its line, the lean, the evidence across weeks, a draft position for 2027 and what is still open; recurring topics outside the themes, proposed as new questions; and the questions with no evidence in the month.
  - One prose call replaces up to eleven.
  - Dropped: the per-cluster syntheses, "Also accumulating", "Theme health" and "Quiet / closed".

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/candidate-verification`: themes' questions get positional ids.
- `vision-watch/weekly-digest`: question tags on stories, early-signal label, ledger, prose-call framing; theme sections kept.
- `vision-watch/monthly-digest`: evidence gate, where each question stands, new topics, unanswered questions.

## Impact

- **Code:**
  - `schemas.py`: question ids on `ThemeDef`, the ledger file schema.
  - `workspace.py`: write and read the ledgers.
  - The digest node: models, prompt, story keys, assembly.
  - The monthly node: rewritten around the ledgers.
  - No new config file, command or service call.
- **Tests:** digest, monthly, schema and workspace tests.
- **Workspace:** ledgers exist only for weeks composed after this lands. Recompose W26–W39 once (about 14 × 10k thinking-model tokens), then compose September's monthly digest.
- **Existing digests:** the archived July and August monthly digests are not recomputed.
