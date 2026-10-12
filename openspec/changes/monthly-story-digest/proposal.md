# Proposal

## Why

The monthly digest walks every qualifying open question and reads like four weekly digests stitched together (August: about 2,800 words, each "evidence" a run of 3-4 cited headlines). It has no memory: the prompt sees only the question text and the month's signals, never what the 2025/2026 Visions said nor how a story moved since last month. It judges the past: `horizon` is recorded on findings but dropped before the monthly, "lean" is which way the month pushed, and "For 2027" reads as policy advice, not where things head. The weekly digest already treats questions as guidance, as tags on stories; the monthly should too.

## What Changes

- **BREAKING.** The monthly digest's unit becomes the story (cluster) that moved in the month, not the open question. Questions and "new topic" become tags on stories, as in the weekly digest; the digest no longer goes through every question.
- Story sections, ranked in code across all lines: short cited evidence with signal and week counts, the story's status change over the month (e.g. emerging -> strengthening), its dominant horizon, how it stands against the Vision (confirms / shifts / contradicts / new ground), where it heads, and the questions it bears on.
- **Against the Vision (A):** each line carries a short, hand-kept statement of what the past Visions said; the prose call compares stories with it.
- **Forward (B):** horizon is read from the stories' findings; a "Where it heads" sentence per story and a "Watch next month" section replace "Still open".
- **Delta (C):** status at month start vs month end, computed in code from the cluster logs; no earlier monthly digest needed.
- **Shorter (D):** about 1,000 words; evidence is one or two sentences, the words go to the Vision comparison, the direction and the 2027 draft lines.
- **Question upkeep (E):** a "Questions to review" section, selected in code: questions with no signal for three or more months, and new topics recurring across months (with a proposed question).
- "For the 2027 draft": a few draft lines, only from stories at strengthening or above.
- Removed: per-question sections, lean, "Thin evidence", "No evidence this month", "Earlier questions".
- The ledger is unchanged; July and August stay archived as they are.

## Validation

A/B prototypes on August 2026 (W32-W35 ledgers) before the specs are written: variants of structure, gate and prompt compared side by side against the archived August digest, until the board finds one really helpful. The chosen variant fixes the gate, ranking, word target and sections in the delta spec.

## Open decisions

- Where "what the Vision said" comes from: a per-line field in `themes.yaml` kept by the board (preferred: deterministic, reviewable), or a `search_vision` lookup through hipeac-mcp at monthly time.
- Ranking across lines (preferred) or grouped by line like the weekly digest.
- The story gate: reuse today's NEW-topic gate (3+ signals in the month, 2 once a candidate trend) for all stories, or tune it on August.
- How many months of quiet make a question "to review".

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/monthly-digest`: story-based sections, evidence gate per story, Vision comparison, horizon and status change, question upkeep; per-question sections removed.
- `vision-watch/candidate-verification`: only if the Vision stance becomes a `themes.yaml` field (theme definition).

## Impact

- **Code:** the monthly node, models and prompt rewritten around stories; `ThemeDef` gains the Vision stance field if chosen; horizon read via the ledger's `finding_ids` from the evidence files.
- **Workspace:** `config/themes.yaml` gains a per-line stance, written by the board; no new files otherwise.
- **Tests:** monthly node and schema tests.
- **Cost:** one prose call per month, as today.
