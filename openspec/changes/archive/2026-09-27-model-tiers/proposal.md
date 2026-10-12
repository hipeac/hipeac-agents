# Proposal

## Why

A day of tests used up the OpenAI credits. The judgement role had been set to the big model in `.env` (and `.env.example`), so thousands of classification calls ran on it; nothing reported usage, so it went unnoticed. The harvest also judged items the per-source cap then discarded, repeated the full theme list in every verdict, and the monthly digest made one big-model call per active cluster.

## Changes

- Models by capability tier, shared by all agents: `LLM_SMALL_MODEL` (harvest), `LLM_BASE_MODEL` (clustering), `LLM_THINKING_MODEL` (digests, defaulting to base). The per-task `OPENAI_*_MODEL` names go.
- Every run names the model of each tier and ends with its token usage per model; the replay dry run estimates tokens.
- Busy sources are picked down to their 8 most notable candidates before the verdict; verdicts run 8 per call; screening calls get a short theme outline.
- The grouping prompt shows old clusters by name only.
- Monthly: full syntheses only for converged stories, at most 10.

## Capabilities

### New Capabilities

### Modified Capabilities

- `platform`, `vision-watch/runs`, `vision-watch/candidate-verification`, `vision-watch/monthly-digest`.
