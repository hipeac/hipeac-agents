# Tasks

## 1. Catalog model

- [x] 1.1 Replace the `SourceClass` literal with catalog-declared classes (`about`, `primary` defaulting to true, optional `weekly_cap`); fail on a source under an undeclared class, naming it; ignore `independence` wherever it appears; update `tests/conftest.py` and every catalog fixture, and add tests for "Class defaults", "Class without defaults", "Legacy independence"; verify `./run pytest tests/agents/vision_watch/test_schemas.py` passes

## 2. Tallies

- [x] 2.1 Resolve entry classes through the current catalog, with the recorded class as fallback, where cluster logs are read (cluster, digest and monthly nodes); rename the outside-catalog fallback `community` to `unlisted`; test "Source reclassified" and "Source removed"; verify `test_cluster.py` and the digest tests pass
- [x] 2.2 Replace `COMMENTARY_CLASSES` with the catalog's `primary` flag, treating `unlisted` as not primary; update the "only commentary" test; verify `test_cluster.py` passes
- [x] 2.3 Remove `independence_share` and its discount from `sort_ranked` and `sort_lead_candidates`; replace `TestIndependenceShare` and `test_low_independence_discounted` with a primary-source tie test; verify `test_cluster.py` passes

## 3. Harvest

- [x] 3.1 Apply the class cap after `_cap_source_volume` (significance, then recency; overflow `source_cap` with a class-cap detail); test "Busy week for AI newsletters" and "Uncapped class"; verify `test_harvest.py` passes

## 4. Monthly

- [x] 4.1 Give the synthesis the share of region-`eu` entries and reword the prompt's EU-only line; test "Europe agreeing with itself"; verify the monthly tests in `test_nodes.py` pass, and that the full suite plus `ruff format` / `ruff check hipeac_agents` are clean

## 5. Live catalog

- [x] 5.1 Copy the live catalog to `config/v1/source-catalog-classes-v1.yaml`; rewrite `config/source-catalog.yaml` with the 14 declared classes and the placements in design.md, and a header saying a class is who is speaking, not the channel; verify it loads with `workspace.read_source_catalog()`
- [x] 5.2 Add `import-ai` (analysis) and `eu-ai-act-newsletter` (analysis) with senders from their past inbox messages, and set `kimi-news` to region global; verify every source id in `evidence/*/findings.json` is in the catalog or is sweep / inbox / board-tip

## 6. Check

- [x] 6.1 On a scratch copy (`--data-dir`), list clusters whose trend status changes under the new catalog (expect the 2 losses and 2 gains in the proposal), then recompose W39 and compare with the live digest; no replay needed
