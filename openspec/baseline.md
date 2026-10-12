# Baseline — 2026-09-26

Sources: hipeac-agents@54b3164 (uncommitted: 1 path, AGENTS.md)

Evidence from the live workspace (`$HIPEAC_AGENTS_DATA_DIR`, weeks 2026-W26–W39) is cited where it shows a finding's effect. W26–W37 were backfilled in one run on 2026-09-12; W38–W39 are the only live harvests.

## Map

| Capability | Scope | Anchors | Clients |
| --- | --- | --- | --- |
| vision-watch/runs | CLI commands, Sat–Fri week + label, `--on` / `--send` / `--limit` / `--only` / `--skip-sweep` / `--data-dir`, crawl preflight, required config, run summary | hipeac_agents/cli.py, agents/vision_watch/cadence.py, workspace.py (config) | operator CLI |
| vision-watch/source-collection | due list; feed, page, newsletter, inbox, board-tip and sweep channels; bot-protected skip; per-source cap; outcomes; scrape cache | nodes/harvest/channels.py, nodes/harvest/node.py, services/crawl.py, services/mail.py | source catalog, harvest mailbox |
| vision-watch/candidate-verification | gate order, judgement verdict, tier ceiling, undated items, URL/near-match folding, re-sample, write-once evidence, replay | nodes/harvest/gates.py, channels.py (gate), node.py (integration), prompts.py, context.py | evidence/<week>/ files |
| vision-watch/clustering | weekly grouping (recorded), cluster identity, append-only logs, trend threshold, ranking | nodes/cluster/, workspace.py (cluster logs) | clusters/ files |
| vision-watch/weekly-digest | sections, lead pick, tips, weak signals, trending, write-once, opt-in send | nodes/digest/ | board mailbox, digests/weekly/ |
| vision-watch/monthly-digest | month weeks, per-cluster synthesis, sections, write-once, opt-in send | nodes/monthly/ | board mailbox, digests/monthly/ |
| platform | skippable services, read-only hipeac-mcp, model roles, rate limits, Sentry | settings.py, services/factory.py, mcp_clients.py, services/vision.py | — |

## Capabilities

| Capability | Reqs | Completeness | Tests | Findings |
| --- | --- | --- | --- | --- |
| vision-watch/runs | 9 | broken | thin | B2 (bug), B4 (bug), B5 (bug), B15 (bug) |
| vision-watch/source-collection | 10 | partial | tested | B6 (gap), B7 (bug), B11 (bug), B13 (bug), B18 (dead), B19 (gap), B20 (question), B22 (bug), B23 (bug), B24 (gap), B25 (gap) |
| vision-watch/candidate-verification | 9 | complete | tested | B8 (question), B9 (bug), B10 (question), B12 (bug) |
| vision-watch/clustering | 7 | complete | tested | B3 (bug), B14 (bug) |
| vision-watch/weekly-digest | 9 | broken | tested | B1 (bug) |
| vision-watch/monthly-digest | 5 | broken | none (node untested; corrected 2026-09-26) | B1 (bug), B21 (question) |
| platform | 5 | complete | tested | B16 (dead), B17 (dead) |

## Findings

### B1 · bug · weekly-digest, monthly-digest · fixed hipeac-agents@268a1b8

A digest composed without `--send` can never be sent. The write-once preflight returns the recorded digest before the send step and never records whether it was sent. Since sending became opt-in (d441e37), the natural flow of compose, review, then `--send` silently mails no one. The test pins "not resent" but not "sendable later".
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/digest/node.py:303-305, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/digest/node.py:357, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/monthly/node.py:289-291, hipeac-agents:tests/agents/vision_watch/test_nodes.py:673
Settle: compose W39 without `--send`, rerun with `--send` against a fake mail client, and check whether a send happens.

### B2 · bug · runs · fixed hipeac-agents@578fd92

A harvest or digest without `--on` targets the week the run date falls in, which from Saturday to Thursday is the week still open. The Sunday 2026-09-20 run wrote a one-day W39 evidence file that then blocked the real W39 harvest (write-once).
Origin: map
Evidence: hipeac-agents:hipeac_agents/cli.py:87-93, hipeac-agents:hipeac_agents/agents/vision_watch/cadence.py:24-33
Settle: run `weekly-harvest` on a Saturday in a scratch workspace and check the target label.

### B3 · bug · clustering · fixed hipeac-agents@fba4241

Redoing a week reuses finding ids (`f-<week>-01`…). The cluster append treats a matching id as "already recorded" and skips it, so the redone week's new findings never enter the clusters, while stale entries under those ids stay. W39 was left with 9 entries whose ids now point at different findings, and the W39 digest was composed from them.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/workspace.py:431-432, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/cluster/node.py:163-164, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/cluster/node.py:182-183
Settle: compare each W39 cluster entry's title with the W39 finding its id names.

### B4 · bug · runs · fixed hipeac-agents@578fd92

`weekly-harvest` ignores `--data-dir` (and `--on`), so a harvest meant for a scratch workspace writes into the configured workspace. Every other command honours the flag.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/cli.py:219-225, hipeac-agents:hipeac_agents/cli.py:206
Settle: `weekly-harvest --data-dir /tmp/x --limit 1` and check where the evidence lands.

### B5 · bug · runs · fixed hipeac-agents@578fd92

Every run, including digest and monthly runs that never crawl, spends a fresh crawl scrape of example.com as a preflight. Such runs abort with "out of credits" when the crawl quota is exhausted.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/cli.py:137-160
Settle: run `weekly-digest` with a crawl client whose scrape raises a quota error.

### B6 · gap · source-collection · fixed hipeac-agents@3dbe10b

arXiv's RSS feeds carry only the latest daily announcement batch and are empty on weekends. Every harvest so far ran on a weekend, so the 8 arXiv sources have produced 0 candidates in 14 weeks. An empty feed is also not distinguished from a quiet source.
Origin: map
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:264-269
Settle: fetch https://rss.arxiv.org/rss/cs.AR on a Saturday: 0 items.

### B7 · bug · source-collection · fixed hipeac-agents@4674f4a

When a feed cannot be fetched, the fallback scrapes the feed URL again instead of the source's page, although the code's comment says "fall back to page scraping".
Origin: spec
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:264-267, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:325
Settle: a fake crawl client records which URL is scraped after a feed fetch returns None.

### B8 · question · candidate-verification · fixed hipeac-agents@dfdf64f

The keyword pre-filter rejects a candidate as off-theme before any judgement when its title and summary hit no theme keyword. The keywords are Vision vocabulary, and in W38–W39, 129 systems-relevant headlines died this way (Intel+ASML High-NA EUV, EC €180M sovereign cloud, IQM quantum deployment). Over 14 weeks, no finding mentions EuroHPC, TSMC, ASML, imec or SiPearl.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:109-111
Settle: decide the pre-filter design (see the themes/gate rework).

### B9 · bug · candidate-verification · fixed hipeac-agents@dfdf64f

Keywords match as raw substrings, so `SAMs` hits "Samsung", `PAI` hits "paid" and "Spain", and short stems hit unrelated words. Candidates then pass the cheap gate on false hits.
Origin: spec
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/gates.py:96
Settle: unit test `keyword_hits("Samsung ships SSD", ["SAMs"]) == 0`.

### B10 · question · candidate-verification · fixed hipeac-agents@dfdf64f

A candidate with no date anywhere passes the window check and is recorded dated the week's Friday. This is how a 2023 paper (PaLM-E) appeared as a W38 finding. The "unknown dates stay in" rule is explicit in the code, but its effect is stale evidence presented as new.
Origin: spec
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/gates.py:64-65, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:142
Settle: product decision: keep, reject, or keep with an "undated" marker.

### B11 · bug · source-collection · fixed hipeac-agents@4674f4a

When a source's channel raises, its outcome is recorded under source id `unknown`, so the run summary no longer says which source failed, even though each outcome is meant to name its source.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/node.py:148-151
Settle: a fake source whose scrape raises: check the outcome's source id.

### B12 · bug · candidate-verification · fixed hipeac-agents@4674f4a

Running out of crawl credits during the re-sample check (a fresh fetch, gathered without exception capture) aborts the harvest after all collection and judgement work. No evidence file is written and the spend is lost.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/node.py:377
Settle: a crawl client that raises a quota error only on fresh fetches.

### B13 · bug · source-collection · fixed hipeac-agents@4674f4a

The sweep appends the literal "past week" to each query, so simulated or backfilled harvests search the present week and their hits fail the window check. The code documents the search as bounded to the harvest window.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:632
Settle: inspect sweep rejects in the backfilled W26–W37: expect mostly out_of_window.

### B14 · bug · clustering · fixed hipeac-agents@4674f4a

When the grouping names an extends-cluster id that does not exist and opens no new cluster, the finding is silently dropped. It counts as "assigned", so it is not reported as unmatched either.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/cluster/node.py:132, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/cluster/node.py:148-155
Settle: a fake grouping plan with an unknown cluster id: check the run notes.

### B15 · bug · runs · fixed hipeac-agents@578fd92

Digest and monthly runs print `findings=0 rejected=0` for a week that has findings, which reads as an empty week.
Origin: map
Evidence: hipeac-agents:hipeac_agents/cli.py:184
Settle: run `weekly-digest` for W39 and read the last line.

### B16 · dead · platform · open

The Vision (hipeac-mcp) client connects on every run, but no node uses it.
Origin: map
Evidence: hipeac-agents:hipeac_agents/services/factory.py:43, hipeac-agents:hipeac_agents/services/vision.py:25-61
Settle: grep for use of the vision service in nodes.

### B17 · dead · cross-cutting · fixed hipeac-agents@350b6c2

Unused helpers: the cluster-log superset check, the recent-findings and latest-weekly-digest readers, a duplicate `_catalog` in the monthly node, and the generic JSON/YAML readers.
Origin: map
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/workspace.py:282, hipeac-agents:hipeac_agents/agents/vision_watch/workspace.py:332, hipeac-agents:hipeac_agents/agents/vision_watch/workspace.py:468, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/monthly/node.py:185, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/monthly/node.py:406, hipeac-agents:hipeac_agents/storage/__init__.py:9-10
Settle: grep for callers.

### B18 · dead · source-collection · fixed hipeac-agents@ccf37ba

The catalog fields `themes`, `last_verified` and `notes` are parsed but never read. The 19 `signals`-stream sources are read by no code: the harvest skips them, and no signals loop exists.
Origin: map
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/schemas.py:143, hipeac-agents:hipeac_agents/agents/vision_watch/schemas.py:152-153, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/gates.py:53
Settle: grep for the fields and the stream value.

### B19 · gap · source-collection · open

Bot-protected sources are always skipped. Escalation is a TODO(v1) with no provider. 6 sources are affected, including all three Anthropic sources, ETSI, CORDIS and IACR ePrint.
Origin: map
Evidence: hipeac-agents:hipeac_agents/settings.py:35-38, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:314-321
Settle: product decision: find alternative feeds, or drop these sources.

### B20 · question · source-collection · open

The board-tip mailbox defaults to `tips@example.com`. If it is unset, tip detection silently stops, and tips are harvested as unattributed newsletter content, without the tip treatment.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/settings.py:11
Settle: decide whether an unset tips mailbox should fail the run or warn.

### B21 · question · monthly-digest · open

The monthly email subject is the bottom-line prose truncated to 100 characters, unlike the weekly "HiPEAC Vision Watch — Week …" subject.
Origin: spec
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/monthly/node.py:362
Settle: decide whether this is intended.

### B22 · bug · source-collection · fixed hipeac-agents@4674f4a

A page-scraped source whose candidates were all rejected is reported as `empty`, while the feed channel reports the same case as `collected`. Quiet and broken sources look the same.
Origin: spec
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:348, hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:286
Settle: compare outcomes for a page source with only out-of-window candidates.

### B23 · bug · source-collection · fixed hipeac-agents@a0430b7

Listing extraction asks for "the most significant developments on the page" (at most 5), not this week's. Many page sources yield only stale items every week: japan-nedo, tsmc-ir, codasip, chips-ju and horizon-wp each had 5–10 out-of-window candidates and 0 in-window in the live weeks. The feed channel filters by the week first, which shows the intent.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/prompts.py:14-16
Settle: re-extract a cached listing page with a "newest dated items" instruction and compare the dates.

### B24 · gap · source-collection · fixed hipeac-agents@3dbe10b

Only the newest 40 feed entries are considered, and high-volume feeds hold just a few days. By Friday, robot-report, sifted, eu-startups, tech-eu, semiconductor-engineering, datacenter-dynamics and servethehome no longer reach back to Saturday, so the early week is lost.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/agents/vision_watch/nodes/harvest/channels.py:181
Settle: check the oldest entry date of each feed on a Friday.

### B25 · gap · source-collection · fixed hipeac-agents@80f4d7e

Source health is not surfaced anywhere beyond the run log. Failing, empty, stale or truncated sources go unnoticed: 28 of 102 evidence sources produced nothing at all in the live weeks, and 14 feeds are empty or failing.
Origin: sweep
Evidence: hipeac-agents:hipeac_agents/cli.py:186-191
Settle: product decision on reporting (see the source-health change).

## Closing notes — 2026-09-26

Worked on branch `feat/vision-watch-2027-signals`. B10 was decided in the forward-looking gate: undated items are rejected, board tips excepted, and newsletter items take their message date. B8/B9 closed by replacing the keyword pre-filter with batched triage. Still open: B16 (Vision client unused), B19 (skipped sources, now listed in the weekly health report), B20 (tips-mailbox default), B21 (monthly subject).
