# Tasks

## 1. Ranking

- [x] 1.1 Add a this-week reach helper and rekey `sort_lead_candidates` (novelty, this-week reach, this-week entries, candidate-trend, momentum); replace the "consequential beats solid" test and add "broad beats loud"; verify `./run pytest tests/agents/vision_watch/test_cluster.py` passes

## 2. Prose call

- [x] 2.1 Drop the significance label from `story_material` (keep source and horizon); add a test that the rendered material carries no "significance"; verify the digest tests pass
- [x] 2.2 Add the "weigh by the open questions, not company size or money" line to `DIGEST_STORIES`, covering stories and the bottom line; verify with a test that the prompt contains it

## 3. Check

- [x] 3.1 On a scratch copy of the workspace (`--data-dir`), recompose W34, W38 and W39 and compare with the live digests: bottom-line topic, agent / lab share of cited findings; verify the ruff checks and the full suite are clean
