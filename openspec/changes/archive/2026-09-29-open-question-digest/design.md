# Design

## Context

The weekly digest node picks at most 4 moving clusters per theme (`story_candidates`) and renders them with findings F1… (`story_material`). One thinking call returns `StoryDigest`, then `compose_digest_markdown` resolves citations, enforces limits and writes the digest and the signals log. The monthly node makes up to 10 cluster syntheses plus a bottom line. `ThemeDef.questions` is a list of strings: 30 questions across the 10 lines. Prototype: `/tmp/vw/proto3.py`, outputs `/tmp/vw/runs/v3-*.md` and `v3-ledger-*.json` (W35–W39, about 38k thinking-model tokens for five weeks plus the monthly).

## Goals / Non-Goals

**Goals:**
- Every weekly story says which open question it moves, and which way, inside the theme sections members already follow.
- The monthly digest gives the board a draft position per question, grounded in weeks of evidence, and shows where the watch is blind.
- Ids, evidence status, thresholds and the unanswered list are code, not model output.

**Non-Goals:**
- Changing harvest, clustering or candidate selection.
- Using the Vision 2026 text. The themes already carry what the board keeps from it. Feeding chapter text as background via hipeac-mcp can come later if positions need it.
- Tracking the board's decisions per question.

## Decisions

### Positional question ids, text recorded in the ledger

`<theme>.<n>` needs no change to `themes.yaml`, which stays plain for the board. The ledger records each question's text, so the monthly counts a signal only while the text still matches. A reworded or reordered question starts fresh, and its old signals stay visible under "Earlier questions". Alternative: explicit ids in `themes.yaml`. Rejected for now because it is more upkeep for the board; the text check covers the risk.

### Story keys and derived status

`story_material` prefixes each candidate with a key (S1…) and already prints its status. The model returns keys, and code maps them to clusters. The early-signal label and the monthly gate read the derived status, never the model's claim.

### Weekly by theme, monthly by question

Board members follow their own lines week to week, so the weekly digest keeps theme sections; the question tag under each story turns it from news into a signal. A story sits under its cluster's theme but may answer another line's question (onboard robot inference in New hardware tagged `physical-ai.2`). The monthly digest is where positions form, so it cuts across themes: questions ordered by evidence, the line shown as a tag. Prototype check: W37 re-rendered in the theme layout from its ledger (`/tmp/vw/render_themes.py`) reads well.

### Two tiers instead of leaving things out

Prototype v4 told the model to leave out "activity" and allowed quiet lines: it used 12 of 25 W39 candidates, emptied Local AI and Society, and dropped the frontier model releases, so the monthly would have reported "no evidence" on the frontier-gap question because of the prompt, not the sources. The per-theme cap was not the cause (it could only bind in 2 themes). v5 keeps the cap of 2 full stories and adds one-line items for the rest: 25/25 and 22/22 candidates used, about 1,200-1,400 words a week, about 150 per theme for a reader following one line. Banning the "rather than" contrast took the hedging from 7 of 10 stories to none.

### Interdisciplinary items, no echoes

A finding tagged with several themes joins clusters in each, so the same link reached 2 themes 3-4 times a week in v5. 6 of the 7 repeats answered a different question in each theme (an EDA item: chiplet standards under New hardware, the engineer's work under AI-built software); these are the interdisciplinary items the board wants to see. Only one echoed the same question. Assembly walks themes in order and drops an item whose findings were all already linked on the same question; a kept repeat is marked "also in <theme>".

Alternative considered: a cross-theme stories part plus a by-theme summary. Rejected for the weekly: members following two lines would read items twice, and the cross-theme view already lives in the bottom line and the monthly digest.

### Structured-output constraint for the monthly

The prototype's monthly answers came back keyed by question text and were all dropped. Restricting the id field to the qualifying ids (a `Literal` built per run) fixed it. Code still drops anything unqualified. The weekly call keeps a plain string, validated after the call, because 30 questions plus NEW would make the schema large.

### Gate within the month

A question qualifies with three signals across two weeks of the month. This keeps the monthly about the month's movement. Cycle-long accumulation is left to reading successive monthlies. Revisit if the board wants a cumulative view.

The first gate (signals in two weeks, or one signal from a story past early) let 22-33 of the 42 questions through in July-September and the digests ran to 3,300-3,700 words. An A/B on those months (`~/.cache/vw/ab/`): "two weeks and one signal past early" kept 14-20 questions, adding 2-signal questions with generic draft positions; "three signals across two weeks" kept 13-16, about 2,400-2,500 words; "three weeks" picked the same questions in August and September. New topics need three signals (two once converged): the looser topic gate let through clusters whose signals shared no development. The same runs moved the evidence limits into "Still open" and banned the contrast phrases, taking the hedges from 25-29 a digest to 1.

### One monthly call

Qualifying questions and topics with their ledger signals go in; answers, new topics and the bottom line come out. This replaces up to 11 thinking calls with one.

## Risks / Trade-offs

- **Questions the watch never answers stay unanswered** (in the prototype: the frontier gap, all of Local AI). → The "No evidence this month" list makes this visible. The fix is upstream (sources, look_for), and the list tells the board where to point it.
- **The draft positions may read as more settled than the evidence.** → Code prints the signal and week counts next to each answer, and single-week answers come from non-early stories only.
- **Ledgers only exist for digests composed after this lands.** → Recompose W26–W39 once.

## Migration Plan

1. Land the code.
2. Recompose W26–W39 on a scratch copy and compare with prototype v3.
3. Install, then compose September's monthly digest.

Rollback: the previous code and digests. Older code ignores the ledgers.
