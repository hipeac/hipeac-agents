# Agent guidance for hipeac-agents

Canonical source of truth for AI coding agents in this repo.
`CLAUDE.md` and `.github/copilot-instructions.md` are symlinks to this file.

## Core philosophy

- Challenge ambiguous, complex, or risky requests; suggest better alternative. Don't follow blindly.
- Maintainability first; KISS & YAGNI; consistency over novelty; self-documenting code, type hints everywhere, comments only for non-obvious _why_.

## Stack

- **Runtime**: Python 3.14, managed with uv. No backend framework — this is a Python library/agent collection, not a web service.
- **Agent framework**: LangGraph for orchestration, LangChain for model/tool primitives. Each agent is a `StateGraph`, not a freeform agent loop.
- **MCP**: MCP **client** — only access path via MCP (`hipeac-mcp` through `langchain-mcp-adapters`' `MultiServerMCPClient`, constructed only in `hipeac_agents/mcp_clients.py`). Plain-HTTP services use provider SDKs directly (`firecrawl-py`, `agentmail`). Never touch the `hipeac-redux` DB — all HiPEAC domain data (Vision search, members, jobs, events) via `hipeac-mcp` read-only tools.
- **Typing/validation**: Pydantic everywhere — graph state, storage schemas, tool I/O.
- **Storage**: local filesystem under a configurable data directory — no DB, no cloud storage, no Redis, no task queue. Adding any is a deliberate decision to revisit, not a default.
- **Observability**: Sentry SDK.

## Commands

A `./run` wrapper exists (`uv run --env-file .env "$@"`). **All project commands must be prefixed with `./run`**. Never call `uv` / `pytest` directly.

```
./run pytest --cov=hipeac_agents --cov-report=term      # full test suite with coverage
./run ruff format .                                     # format
./run ruff check hipeac_agents                          # lint (must be clean before commit)
```

## Commit conventions

## Commit conventions

Conventional Commits: `type(scope): description` — imperative, lowercase, no trailing period, one line, no attribution trailers. Types: `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `perf`. Breaking: `feat!:` / `BREAKING CHANGE:` footer. Never vague (`wip`, `update`).

## Git workflow

- Always branch from `main`. Never branch from another feature branch.
- Branch naming: `type/short-description` in kebab-case (`feat/vision-watch-harvest`, `fix/cluster-threshold`).

## Python

- PEP 8; type hints on all signatures.
- Docstrings (public functions/methods/modules): reST, Sphinx-compatible; no type info — it's in the signature; `:param` / `:returns` / `:raises` end with a period.

### Testing (pytest)

### Testing (pytest)

- All new code requires tests. Tests live in `tests/`, mirroring the package structure, never inline next to source.
- `pytest-asyncio` is in `auto` mode — async tests (graph nodes, MCP calls) need no marker.
- Anything touching the filesystem or external services must be guarded/mocked. Never hit the production data directory or live APIs/mailboxes in tests.
- Markers, addopts, and coverage config live in `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`) — don't restate them here.

#### Test-review workflow

1. Read tests first; fix weak assertions before running.
2. Run adjusted suite — failure after adjustment means real bug.
3. Fix production code; never weaken a test to force green.

### Ruff

- Ruff handles linting + formatting; rule sets, `target-version`, `line-length`, per-file ignores live in `pyproject.toml` — no inline-ignores without justification comment. `./run ruff format . && ./run ruff check hipeac_agents` before commit.

## LangGraph / LangChain

### Agent layout

- One subpackage per agent under `hipeac_agents/agents/<agent_name>/`: `graph.py`, `state.py`, `nodes/`.
- Node service boundaries enforced: nodes receive already-built clients, only what their protocol exposes (e.g. pure grouping/tallying node gets none; digest node gets `mail` send plus read-only `vision`). Never pass a node more clients than its skill-design counterpart allows.
- Judgement-free logic (gates, tallies, thresholds, ranking): plain synchronous type-hinted code, callable without an LLM. Prompts handle only judgement (relevance, tiering, grouping, prose).

### Service layer

- `hipeac_agents/services/` is the provider-agnostic boundary: `crawl.py` (Firecrawl), `mail.py` (AgentMail), `vision.py` (`hipeac-mcp` over MCP). Protocols first; one provider class per service.
- `hipeac_agents/services/factory.py` is the only place providers are chosen; each service independently configurable/skippable via `settings.py` env vars, so tests and partial local setups never require all services live.
- SDK clients are sync, wrapped with `asyncio.to_thread`; tests fake the SDK object (the boundary), never live services.

### MCP client boundary

- `hipeac_agents/mcp_clients.py` is the only place `MultiServerMCPClient` is constructed. Nodes and the CLI never import provider SDKs or `mcp_clients.py` — providers are wired in `services/factory.py` only.
- If a feature needs new HiPEAC data, add the tool to `hipeac-mcp`, don't reach around it.

### Data model conventions

Module names encode a model's lifecycle: `schemas.py` = persisted workspace files, `state.py` = one run's graph state, `nodes/*/models.py` = LLM structured-output models (paired with `prompts.py`). Never mix: a persisted type never lives in `state.py`; an LLM-output type never lives in `schemas.py`.

## Error monitoring (Sentry)

Use the Sentry MCP server to investigate errors proactively when debugging.

- **`regionUrl`**: `https://de.sentry.io`
- **`organizationSlug`**: `ea06`
- **`projectSlugOrId`**: `hipeac-agents`

Prefer **`resolvedInNextRelease`** over `resolved` — the fix ships with the next deployment rather than being marked live.

### Bug fix workflow

When a Sentry issue reveals a bug not covered by an existing test, add a regression test before (or alongside) the fix:

1. **Reproduce first**: write a test that fails against current code, confirming you have isolated the root cause.
2. **Fix the code**: make the test pass.
3. **Verify no new gaps**: confirm no related paths are left uncovered.

Never close a Sentry bug without a corresponding regression test.
