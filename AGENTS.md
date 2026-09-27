# Agent guidance for hipeac-agents

Canonical source of truth for AI coding agents in this repo.
`CLAUDE.md` and `.github/copilot-instructions.md` are symlinks to this file.

## Core philosophy

- Challenge ambiguous, complex, or risky requests; suggest better alternative. Don't follow blindly.
- Maintainability first; KISS & YAGNI; consistency over novelty; self-documenting code, type hints everywhere, comments only for non-obvious _why_.

## Stack

- **Runtime**: Python 3.14, uv. Library/agent collection, not a web service.
- **Agents**: LangGraph `StateGraph` per agent (no freeform agent loop); LangChain for model/tool primitives; Pydantic for state, schemas, tool I/O.
- **Storage**: local filesystem under a configurable data directory — no DB, cloud storage, Redis or task queue. Adding any is a deliberate decision, not a default.
- **Observability**: Sentry SDK.

## Commands

All project commands via `./run` (loads `.env`). Never call `uv` / `pytest` directly. `ruff format` + `ruff check hipeac_agents` clean before commit; tool config lives in `pyproject.toml`, no inline ignores without a justification comment.

## Commit conventions

Conventional Commits: `type(scope): description` — imperative, lowercase, no trailing period, one line, no attribution trailers. Types: `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `perf`. Breaking: `feat!:` / `BREAKING CHANGE:` footer. Never vague (`wip`, `update`).

## Git workflow

Branch + PR for sensitive areas — auth, permissions, serializers / schemas, payments, security settings, CI workflows — or when in doubt; everything else may go straight to `main`. Never merge your own PR.

## Specs

`openspec/specs/` is source of truth for behaviour; spec-driven changes via OpenSpec (`openspec/changes/`).

## Python

- PEP 8; type hints on all signatures.
- Docstrings (public functions/methods/modules): reST, Sphinx-compatible; no type info; `:param` / `:returns` / `:raises` end with a period.

### Testing (pytest)

- All new code requires tests, in `tests/` mirroring the package structure.
- Reuse `tests/conftest.py` and `tests/agents/vision_watch/_fakes.py`; don't redefine fakes.
- Mock the filesystem and external services. Never hit the production data directory or live APIs/mailboxes.

When asked to review / audit / add tests:

1. Read tests first; fix weak assertions before running.
2. Run adjusted suite — failure after adjustment = real bug.
3. Fix production code; never weaken a test to force green.

## LangGraph

### Agent layout

- One subpackage per agent under `hipeac_agents/agents/<agent_name>/`: `graph.py`, `state.py`, `nodes/`.
- Nodes receive already-built clients, only what they need (a pure grouping/tallying node gets none; the digest node gets `mail` send plus read-only `vision`).
- Judgement-free logic (gates, tallies, thresholds, ranking): plain synchronous code, callable without an LLM. Prompts handle only judgement (relevance, grouping, prose).

### Services

- `hipeac_agents/services/` is the provider boundary (crawl, mail, vision): protocol first, one provider class each. SDK calls wrapped in `asyncio.to_thread`; tests fake the SDK object.
- Providers are chosen only in `services/factory.py`, each skippable via `settings.py` env vars. Nodes and the CLI never import provider SDKs or `mcp_clients.py`.
- HiPEAC data (Vision, members, jobs, events) comes only from `hipeac-mcp` read-only tools. Never touch the `hipeac-redux` DB; if new data is needed, add the tool to `hipeac-mcp`.

### Data model conventions

Module names encode a model's lifecycle: `schemas.py` = persisted workspace files, `state.py` = one run's graph state, `nodes/*/models.py` = LLM structured-output models (paired with `prompts.py`). Never mix: a persisted type never lives in `state.py`; an LLM-output type never lives in `schemas.py`.

## Error monitoring (Sentry)

Use the Sentry MCP server to investigate errors proactively when debugging.

- **`regionUrl`**: `https://de.sentry.io`
- **`organizationSlug`**: `ea06`
- **`projectSlugOrId`**: `hipeac-agents`

Prefer **`resolvedInNextRelease`** over `resolved` — fix ships with next deployment.

### Bug fix workflow

Sentry issue reveals a bug not covered by an existing test — add regression test before/alongside the fix:

1. Reproduce first: failing test against current code, confirming root cause.
2. Fix code to pass.
3. Verify no related paths left uncovered.

Never close a Sentry bug without a corresponding regression test.
