# hipeac-agents

AI agent collection for [HiPEAC](https://www.hipeac.net), built on [LangGraph](https://langchain-ai.github.io/langgraph/). Each agent is a `StateGraph` with an explicit node pipeline, not a freeform agent loop.

There is no web service and no database: agents read and write plain file under a configurable data directory.

## Agents

### vision-watch

A forward-looking signal detector for the [HiPEAC Vision](https://www.hipeac.net/vision/) editorial board: it watches the technology landscape and mails a weekly digest of what is brewing — new advances, legislation and programmes in the pipeline, dependencies and risks — read as signals inside the Vision's broad lines (its themes).

The pipeline is `harvest -> health` and `cluster -> digest`, with a separate `monthly` node for the month-end synthesis:

| Node      | What it does                                                                                                                    |
| --------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `harvest` | Collects from the source catalog, arXiv, the tips mailbox and a web sweep; triages and judges each candidate against the themes |
| `health`  | Labels every source (failing, empty, stale, silent…) and emails the dev list when the picture changes                         |
| `cluster` | Groups findings into cross-week clusters, one file per theme, append-only                                                    |
| `digest`  | Writes the week as a few short stories per theme, with the findings linked inline, and mails it                              |
| `monthly` | Synthesises a calendar month from the weekly evidence                                                                           |

The editorial week runs **Saturday through Friday**; a digest is labelled by the ISO week of its closing Friday, e.g. `2026-W37`. Without `--on`, a run targets the most recently closed week: on a Saturday, the week that ended the day before.

Judgement-free logic — gates, tallies, thresholds, ranking — is plain deterministic Python, callable without an LLM. Prompts are reserved for genuine judgement: relevance, significance, grouping, prose.

## Usage

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
cp .env.example .env    # then fill in the keys you need
```

Every command goes through the `./run` wrapper, which loads `.env` and invokes `uv run`, resolving dependencies on first use.

```sh
./run python -m hipeac_agents weekly-harvest            # Friday evening or later
./run python -m hipeac_agents weekly-digest
./run python -m hipeac_agents monthly-digest --month 2026-08
./run python -m hipeac_agents snapshot-feeds            # daily, so busy feeds keep their whole week
```

Useful flags:

| Flag              | Effect                                                |
| ----------------- | ----------------------------------------------------- |
| `--on 2026-09-11` | Run for the week containing this date (backfilling)   |
| `--send`          | Digest: email the board. Harvest: email source-health changes to the dev list (opt-in) |
| `--redo`          | Back the week up and redo it (clears its cluster entries) |
| `--limit N`       | Check at most N sources — cheap partial harvests      |
| `--only id1,id2`  | Check only these source ids                           |
| `--skip-sweep`    | Drop the general per-theme search sweep               |
| `--data-dir PATH` | Override `HIPEAC_AGENTS_DATA_DIR` for one run         |

`simulate-harvest` is `weekly-harvest` with a mandatory `--on`, for replaying a past window.

A digest composed without `--send` can be reviewed and sent later with `--send`; it is never sent twice.

The weekly digest is written for the editorial board: a short bottom line, then at most two stories per theme, each a few sentences with the evidence linked inline, the board tips, and any story that newly converged. Quiet themes are named in one line. Every finding of the week is kept in the signals log beside the digest, so the digest can stay short.

## The data directory

`HIPEAC_AGENTS_DATA_DIR` points at a workspace the repository does not carry:

```
config/                 themes.yaml, source-catalog.yaml (human-owned)
evidence/<week>/        findings.json, rejected.json, grouping.json, sources.json, health.json/.md (write-once)
clusters/               one file per theme, append-only, cross-week
digests/weekly/         digest-YYYY-Www.md (write-once), its .sent.json marker, and -signals.md (every finding)
digests/monthly/        digest-YYYY-MM.md (write-once) and its .sent.json marker
cache/scrapes/          content-addressed crawl cache
cache/feed-snapshots/   the open week's feed entries, captured daily
_backup/                weeks set aside by --redo
```

The themes and the source catalog are **editorial input, owned by a human** — the agent never rewrites them. Evidence and digests are write-once: redo a week with `--redo`, which backs everything up first.

`themes.yaml` lists the Vision's broad lines: each theme has an id, a plain-words `description`, the open `questions` the next Vision asks in it, what to `look_for` (real-world names: programmes, companies, laws — news never uses the Vision's vocabulary), optional `keywords` as hints, and a distinct `sweep_query`. An item is relevant when it is a signal inside a theme.

`source-catalog.yaml` groups sources under their class, which sets their default `independence` (stories resting on low-independence sources are discounted):

```yaml
classes:
  programmes: {independence: high}
sources:
  programmes:
    - {id: uk-aria, url: https://aria.org.uk/insights}
  preprints:
    - {id: arxiv-cs-ar, url: https://arxiv.org/list/cs.AR/new, arxiv: cs.AR}
```

The channel follows from the fields: `arxiv` (API, any date range), `feed_url` (RSS/Atom), otherwise the page is scraped; `senders` adds the newsletter channel and `web: false` makes it newsletter-only; `skip: <reason>` never checks the source.

### Re-judging past weeks

`replay-gate --from 2026-W26 --to 2026-W39 [--dry-run]` runs the current gate over recorded weeks, from what is on disk (no scraping), and writes the result plus a review `report.md` under `replay/`. After review, `replay-gate --apply <folder>` archives `evidence/` and `clusters/` as `-v1` and re-clusters the replayed weeks.

A fresh clone therefore harvests nothing until you supply a `config/` directory of your own.

## Models

Models are configured by capability tier, shared by every agent, never by task:

| Tier       | Default model (reasoning) | vision-watch uses it for                                     |
| ---------- | ------------------------- | ------------------------------------------------------------ |
| `small`    | `gpt-6-luna` (`none`)     | harvest: triage, picks, verdicts — hundreds of calls a week  |
| `base`     | `gpt-6-sol` (`low`)       | clustering — one call a week                                 |
| `thinking` | `gpt-6-sol` (`low`)       | weekly digest (one call), monthly syntheses (at most 11)     |

Each tier is set with `LLM_<TIER>_MODEL` and `LLM_<TIER>_REASONING`. An empty reasoning value sends none, for models without reasoning. `temperature=0` is sent only when reasoning is off, because reasoning models reject it otherwise.

`LLM_PROVIDER` picks the provider (default `openai`). Every run prints the model of each tier and ends with its token usage per model; `replay-gate --dry-run` estimates tokens before spending any.

## Services

Agents depend on protocols, never on providers directly. Each service is configured by its own environment variable, and skipped when unset.

| Service  | Provider     | Used for                                   |
| -------- | ------------ | ------------------------------------------ |
| `crawl`  | Firecrawl    | Scraping and searching sources             |
| `mail`   | AgentMail    | The tips mailbox, and sending digests      |
| `vision` | `hipeac-mcp` | HiPEAC Vision, members, events (read-only) |

## Development

```sh
./run pytest --cov=hipeac_agents --cov-report=term
./run ruff format .
./run ruff check hipeac_agents
```

See [AGENTS.md](AGENTS.md) for the full conventions.
