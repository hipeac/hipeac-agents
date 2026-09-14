# hipeac-agents

AI agent collection for [HiPEAC](https://www.hipeac.net), built on [LangGraph](https://langchain-ai.github.io/langgraph/). Each agent is a `StateGraph` with an explicit node pipeline, not a freeform agent loop.

There is no web service and no database: agents read and write plain file under a configurable data directory.

## Agents

### vision-watch

Tracks the technology landscape behind the [HiPEAC Vision](https://www.hipeac.net/vision/), and mails the editorial board a weekly digest of what actually moved.

The pipeline is `harvest -> cluster -> digest`, with a separate `monthly` node for the month-end synthesis:

| Node      | What it does                                                                                                                  |
| --------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `harvest` | Sweeps the source catalog and the tips mailbox, verifies each candidate against the themes, and records findings for the week |
| `cluster` | Groups findings into cross-week clusters, one file per theme, append-only                                                     |
| `digest`  | Composes the weekly markdown digest and mails it                                                                              |
| `monthly` | Synthesises a calendar month from the weekly evidence                                                                         |

The editorial week runs **Saturday through Friday**; a digest is labelled by the ISO week of its closing Friday, e.g. `2026-W37`.

Judgement-free logic — gates, tallies, thresholds, ranking — is plain deterministic Python, callable without an LLM. Prompts are reserved for genuine judgement: relevance, tiering, grouping, prose.

## Usage

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/).

```sh
cp .env.example .env    # then fill in the keys you need
```

Every command goes through the `./run` wrapper, which loads `.env` and invokes `uv run`, resolving dependencies on first use.

```sh
./run python -m hipeac_agents weekly-harvest
./run python -m hipeac_agents weekly-digest
./run python -m hipeac_agents monthly-digest --month 2026-08
```

Useful flags:

| Flag              | Effect                                                |
| ----------------- | ----------------------------------------------------- |
| `--on 2026-09-11` | Run as if it were this date (backfilling a past week) |
| `--skip-send`     | Compose and write the digest, but send no email       |
| `--limit N`       | Check at most N sources — cheap partial harvests      |
| `--only id1,id2`  | Check only these source ids                           |
| `--skip-sweep`    | Drop the general per-theme search sweep               |
| `--data-dir PATH` | Override `HIPEAC_AGENTS_DATA_DIR` for one run         |

`simulate-harvest` is `weekly-harvest` with a mandatory `--on`, for replaying a past window.

## The data directory

`HIPEAC_AGENTS_DATA_DIR` points at a workspace the repository does not carry:

```
config/                 themes.yaml, source-catalog.yaml (human-owned)
evidence/<week>/        findings.json, rejected.json (write-once)
clusters/               one file per theme, append-only, cross-week
digests/weekly/         digest-YYYY-Www.md (write-once)
digests/monthly/        digest-YYYY-MM.md (write-once)
cache/scrapes/          content-addressed crawl cache
```

The themes and the source catalog are **editorial input, owned by a human** — the agent never rewrites them. Evidence and digests are write-once: re-running a week means deleting that week's files first, deliberately.

A fresh clone therefore harvests nothing until you supply a `config/` directory of your own.

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
