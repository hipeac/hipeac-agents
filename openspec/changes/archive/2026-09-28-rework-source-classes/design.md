# Design

## Context

Classes feed four things: reach (distinct classes), the primary-source rule (`COMMENTARY_CLASSES = {"aggregators", "community"}` in `tallies.py`), novelty (new classes this week) and, after `digest-rank-without-significance`, story ranking. The list of classes is a closed `SourceClass` literal in `schemas.py`. Cluster entries record `source_class` when they are written. Findings from outside the catalog (sweep, inbox, board tips) get `community` in `cluster/node.py`. The per-source cap keeps at most 4 findings per source after the verdict.

## Goals / Non-Goals

**Goals:**
- Each class answers one question, "who is speaking?", so that 3 classes really means 3 independent kinds of voice.
- Class meaning and roles live in the human-owned catalog, not in code.
- Reclassifying a source is a catalog edit and needs no migration.

**Non-Goals:**
- Multi-attribute tagging (actor × topic × channel).
- Changing the candidate-trend numbers (4 findings, 3 classes, 3 weeks).
- Newsletter tracking links (see `ideas.md`).

## Decisions

### A class is a kind of voice; the channel is separate

Feed, page, arXiv and email are already separate (`feed_url`, `arxiv`, `senders`, `web`). "Newsletter" was doing double duty as a class (`aggregators`) and a channel. It is only a channel now: SemiAnalysis's newsletter is analysis, Sifted's is press, TLDR's is ai-news.

### Primary or not, declared per class

Primary means the actor announces its own work: a funder its call, a company its chip, a lab its model, a paper its result. Non-primary classes report or comment on others' news. The catalog marks those with `primary: false`, replacing the hard-coded `COMMENTARY_CLASSES`. Two roles are enough; "reporting" and "commentary" would behave the same, so they are not separate roles.

### Taxonomy

| class | primary | about | sources |
|---|---|---|---|
| eu-institutions | yes | EU-level bodies and programmes | ted-europa, cordis-europa, eurohpc-ju, chips-ju, ec-digital-strategy, eu-ai-office, horizon-wp, eu-defence-industry-space |
| programmes | yes | governments and public funders, national or non-EU | darpa-news, darpa-opportunities, nsf-news, nist-chips-america, uk-aria, japan-nedo, korea-msit, china-miit |
| research | yes | universities and research institutes | imec-stories, mpi-intelligent-systems, ethz-ai, stanford-hai, allenai, mit-media-lab |
| papers | yes | research papers, preprints and journals | arxiv-cs-* (8), iacr-eprint, huggingface-daily-papers, science-robotics |
| standards | yes | standards bodies, consortia, industry associations | riscv-intl, etsi-news, ietf, w3c-news, ucie, cxl, threegpp, ocp-specifications, semi-org |
| open-source | yes | open-source foundations | open-source-initiative, eclipse-foundation, openhw-group, cncf |
| ai-labs | yes | AI model developers | openai-news, deepmind-blog, anthropic-news, anthropic-research, anthropic-economic-index, meta-ai-research, mistral-news, kimi-news, apertus-ai, prismml-news, amilabs-updates, huggingface-blog |
| companies | yes | company newsrooms and investor relations | nvidia-news, apple-news, intel-newsroom, tsmc-ir, asml-ir, samsung-semi, sipearl, axelera-ai, codasip, black-semiconductor, neura-robotics, agile-robots, anybotics, onex-technologies, cognition-ai, cactuscompute-research, exein-cra |
| infrastructure-energy | yes | energy and data-centre agencies and analysts | iea-data-centres, uptime-institute, ember-energy |
| foresight | yes | think tanks and foresight units | ainow, jrc-policy-lab, espas, oecd-ai, oecd-newsroom, uk-go-science, sg-csf, iftf, ftsg-outlook, asu-csi |
| press | no | journalism: trade, tech and startup press | semiconductor-engineering, ee-times-europe, next-platform, servethehome, datacenter-dynamics, robot-report, automated-warehouse, wired-ai-lab, sifted, eu-startups, tech-eu, science-business, bits-chips |
| analysis | no | independent expert analysis and measurement | semianalysis, fabricated-knowledge, interconnects-ai, hyperdimensional, import-ai, eu-ai-act-newsletter, chinatalk, followthegradient, artificialanalysis, arcprize |
| ai-news | no, cap 6 | curated AI-news digests | tldr-ai-hardware, forward-future, the-rundown-ai, ai-breakfast, future-tools, deeplearning-the-batch |
| commentary | no | forums, opinion blogs, podcasts | hacker-news, lesswrong-af, reddit-localllama, reddit-ml, garymarcus, dwarkesh-podcast, lex-fridman |

W26–W39 findings under this map: press 207, ai-news 142, papers 61, research 49, eu-institutions 49, analysis 48, companies 33, standards 32, ai-labs 15, others ≤ 7; outside the catalog: sweep 28, inbox 27, board tips 6.

Alternatives considered:
- **Keep `capital` for money news.** Rejected. Funding news comes from press (Sifted, EU-Startups, Tech.eu) and company IR, so a money class would mix actors. Money is a topic, not a voice.
- **Merge eu-institutions into programmes and rely on `region`.** Rejected. For a European roadmap, EU policy and non-EU funders converging on something are two independent signals, and should count as two classes.
- **Keep `ai-labs` inside `companies`.** Rejected. The labs are the loudest voice. Keeping them as one class means OpenAI and DeepMind agreeing counts once, not as independent evidence.
- **Split press into trade and startup press.** Deferred. It would bring back the reach that `european-startup-capital` loses, which is the echo we want to discount.

### Classes read from the current catalog

Tallies resolve an entry's class by `source_id` through the catalog, and fall back to the recorded class when the source is gone. The resolution happens once where cluster logs are read (cluster, digest and monthly nodes), so the tally functions keep taking entries. Alternative: a one-off migration that rewrites `source_class` in the logs. Rejected. It breaks append-only logs and has to be repeated on every later reclassification.

### Outside-catalog findings

Sweep, inbox and board-tip findings resolve to a single non-primary pseudo-class, as today (`community`). It is renamed `unlisted` so it is not confused with the commentary class. It adds one class of reach and never makes a cluster primary.

### Class cap

Applied after `_cap_source_volume`, on the same order (significance, then recency). It needs no new model call. Overflow reuses the `source_cap` reason with the detail "class cap: kept N of M in ai-news", so `replay-gate`, which re-judges `source_cap` rejects, needs no change. `ai-news: 6` roughly halves its current weekly average.

### Independence folded in

Same reasoning as the tier removal: reach over clearly defined classes is the independence signal. The monthly check keeps its purpose through the share of `region: eu` entries, which every entry already records.

## Risks / Trade-offs

- [Trend status shifts] → free check on current clusters: 26 stay converged, 2 lose it, 2 gain it. The "Newly converged" section may re-announce the two that gain it.
- [Judgement calls in the map] → the catalog is human-owned and a move is one edit with no migration; see Open Questions.
- [Class list no longer checked by the type checker] → the catalog is validated on read: an undeclared class fails, naming it.
- [Old catalogs] → `independence` is ignored. A catalog with no `classes` map fails, because every class must be declared. The live catalog is rewritten in the same step.

## Migration Plan

1. Land the code with the new catalog format.
2. Rewrite the live `config/source-catalog.yaml` (keep a copy as `config/v1/source-catalog-classes-v1.yaml`).
3. Recompose W39 on a scratch copy and check the status shifts listed above.

Rollback: restore the catalog copy and the previous code; no workspace data is rewritten.

## Resolved placements (2026-09-28)

- ArcPrize and Artificial Analysis: analysis. `research` is kept for research institutes working in the Vision's areas.
- SEMI: standards.
- Hugging Face blog: ai-labs, since it publishes its own models and model tooling. Undecided; revisit if its findings read as platform or company news.
- Foresight stays primary.
