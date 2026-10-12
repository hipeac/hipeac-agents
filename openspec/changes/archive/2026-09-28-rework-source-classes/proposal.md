# Proposal

## Why

Source classes are what the watch counts as independent evidence: a candidate trend needs 3 classes and a primary source, novelty rewards new classes, and `digest-rank-without-significance` ranks stories by the classes they reach. Yet the classes were inherited from v1 and never defined. `capital` holds TSMC, ASML, Intel and Samsung plus imec (a research institute) and Fabricated Knowledge (a newsletter), while NVIDIA sits in `companies`. Research institutes are split across `programmes`, `capital`, `ai-labs` and `foresight`. `aggregators` mixes trade journalism, expert analysis and AI-news digests (24 sources). The AI-news digests alone supply about 20% of W26–W39 findings and about 45% of what digest stories cite. The per-class independence setting (high / med / low) tried to patch over this and decides almost nothing. Only `eu-uptake` is low, and the AI newsletters were marked high.

## What Changes

- A class is a kind of voice, i.e. who is speaking, not a channel. A newsletter belongs to the class of whoever writes it.
- The catalog declares every class with a one-line `about`. `primary: false` marks classes that report on or comment on others' news. A class may set a `weekly_cap`. The class list moves from code to the catalog; a source under an undeclared class fails to read.
- New taxonomy of 14 classes (see design): eu-institutions, programmes, research, papers, standards, open-source, ai-labs, companies, infrastructure-energy, foresight (primary); press, analysis, ai-news, commentary (not primary). `capital`, `aggregators`, `eu-uptake`, `preprints` and `community` go away.
- Class volume cap: the sources of a class together keep at most `weekly_cap` findings a week, after their own caps. `ai-news` starts at 6.
- Tallies read each entry's class from the current catalog, so a reclassified source counts in its new class for all past weeks, without rewriting the append-only logs.
- **BREAKING (catalog)**: independence is removed: from the catalog, the standing ranking, story selection and the monthly synthesis. The monthly "Europe agreeing with itself" check uses the share of region-`eu` entries instead. Catalogs that still carry independence keep reading.
- Catalog gaps fixed: `import-ai` and `eu-ai-act-newsletter` produced findings in W27–W37 but are not in the catalog; `kimi-news` is marked region `eu` but Moonshot AI is Chinese.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/source-collection`: Catalog format (declared classes, `about`, `primary`, `weekly_cap`, no independence); new Class volume cap.
- `vision-watch/clustering`: primary source from the class's `primary` flag; standing ranking without independence; new requirement that tallies read classes from the current catalog.
- `vision-watch/weekly-digest`: Story selection without the independence tie-breaker.
- `vision-watch/monthly-digest`: synthesis given the European share instead of the low-independence share.

## Impact

- Code: `schemas.py` (`SourceClass` literal → catalog-declared, class settings, independence out), `nodes/cluster/tallies.py` (`COMMENTARY_CLASSES`, `independence_share`, rankings), `nodes/cluster/node.py` (fallback class for sweep / inbox / board tips), `nodes/harvest/node.py` (class cap), `nodes/monthly/node.py` + `prompts.py`, and the digest and monthly nodes where cluster logs are read.
- Tests: conftest catalog fixture and every catalog fixture; `test_schemas.py`, `test_cluster.py`, `test_harvest.py`, monthly tests in `test_nodes.py`.
- Live `config/source-catalog.yaml`: rewritten under the new classes (human-owned; reviewed before it lands).
- Trend status on current clusters (free check, old vs new classes): 26 stay converged, 2 lose it (`european-startup-capital`, which rests on startup press only; `industrial-robot-deployment`), 2 gain it (`high-performance-interconnect-bottlenecks`, `hpc-accelerator-competition`).
- `digest-rank-without-significance` rewrites Story selection after this change; land this one first.
- Supersedes the drafts `drop-source-independence` and `ai-news-as-leads`.
