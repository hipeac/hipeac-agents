# Proposal

## Why

The weekly digest roughly doubles the agent / frontier-lab share of the evidence: 21% of the W26–W39 pool mentions agents or LLMs, 40% of the findings the stories cite do; lab-named findings go from 15% to 30%, and 7 of 14 bottom lines lead with a lab or agent story. The cause is the small model's significance score. It rates lab news higher (mean 3.12 vs 2.59; 28% vs 9% scored 4), and story selection ranks on it first, then shows it to the prose call as "significance 4", which anchors the bottom line. A vendor-swap test (OpenAI ↔ Anthropic names swapped in W34) kept the same lead, so the pull is the score and the event, not the model's own vendor. In a scratch test (W34, W39), ranking without significance, hiding the labels and one prompt line moved W34's bottom line from OpenAI's Ohio deal to open models closing the gap.

## What Changes

- Story candidates are ranked by novelty, then source classes reached this week, then entries this week, then candidate-trend status, then momentum. The small model's significance no longer ranks stories (it still picks each candidate's findings and still drives the harvest's source cap).
- The prose call no longer sees significance scores.
- The prose call is told to weigh a development by what it changes for the theme's open questions, not by the size of the company or the money involved.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/weekly-digest`: Story selection ranking; new requirement on what the prose call judges by.

## Impact

- `nodes/cluster/tallies.py` (`sort_lead_candidates`, plus a this-week reach helper), `nodes/digest/node.py` (`story_material`), `nodes/digest/prompts.py`.
- Tests in `tests/agents/vision_watch/test_cluster.py` and `test_nodes.py` (digest).
- Written against the Story selection text after `rework-source-classes` (no independence tie-breaker); land that change first.
- Past digests stay as written (write-once).
