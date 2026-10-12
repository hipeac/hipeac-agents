# Proposal

## Why

The watch exists to feed the 2027 Vision, which looks forward: what is brewing matters more than what happened. The pipeline scored the past. A substring keyword pre-filter built from Vision jargon dropped relevant news before any judgement (129 systems-relevant headlines in two weeks), undated items passed as new, and the lead story went to the biggest cluster.

## Changes

- Themes become watch questions (question, why, look_for; keywords only hints).
- One batched triage call per source replaces the keyword pre-filter; only kept items are scraped and judged.
- The verdict adds direction, horizon and a forward note; significance means forward importance for Europe; tier is confidence only.
- Undated items and round-ups are rejected (newsletter items take their message date).
- The digest leads with the most forward-significant, most novel cluster, adds "What's brewing", and shows movement per question.
- `replay-gate` re-judges recorded weeks offline, for review, and installs the result.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/candidate-verification`: triage, verdict, undated and round-up rejects; keyword matching removed.
- `vision-watch/weekly-digest`: sections, lead, question headings.
- `vision-watch/source-collection`: sweep triages hits; newsletter items dated by their message.
- `vision-watch/runs`: replay-gate.
