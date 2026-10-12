# platform Specification

## Purpose

Collection-wide behaviour shared by every agent: how external services are configured and skipped, which language models run which judgements, and how errors are reported.

## Requirements

### Requirement: Independently skippable services

Each external service SHALL be enabled only by its own configuration and skipped when unconfigured: crawl (Firecrawl, by API key), mail (AgentMail, by API key) and Vision knowledge (hipeac-mcp, by URL). A skipped service SHALL never stop an agent from running the parts that don't need it.

#### Scenario: No crawl key

- **WHEN** no Firecrawl key is configured and a harvest runs
- **THEN** every due source is reported as failed with "crawl service not configured", and the run completes

#### Scenario: Vision server unreachable

- **WHEN** the hipeac-mcp URL is set but the server cannot be reached
- **THEN** the Vision service is treated as unconfigured and the run continues

### Requirement: Read-only HiPEAC data

All HiPEAC domain data SHALL be read through hipeac-mcp's read-only Vision tools (search, overview, article). The system SHALL never write to HiPEAC systems.

#### Scenario: Tool scope

- **WHEN** the Vision service connects
- **THEN** only the Vision search, overview and article tools are made available

### Requirement: Model tiers

Models SHALL be configured by capability tier, shared by every agent, each with a reasoning effort: a small model for high-volume classification (`LLM_SMALL_MODEL`, default `gpt-6-luna`, reasoning `none`), a base model for everyday judgement (`LLM_BASE_MODEL`, default `gpt-6-sol`, `low`), and a thinking model for the few calls whose output people read (`LLM_THINKING_MODEL`, default `gpt-6-sol`, `low`). The provider is `LLM_PROVIDER`. An empty reasoning value SHALL send no reasoning parameter. Temperature 0 SHALL be sent only when reasoning is off or not sent, since reasoning models reject it otherwise.

#### Scenario: Default models

- **WHEN** no tier is configured
- **THEN** the harvest runs on `gpt-6-luna` without reasoning and at temperature 0, clustering and the digests on `gpt-6-sol` at low reasoning and without a temperature

#### Scenario: Model without reasoning

- **WHEN** a tier is set to `gpt-4o-mini` with an empty reasoning value
- **THEN** it is called at temperature 0 with no reasoning parameter

#### Scenario: Old per-task names

- **WHEN** `.env` still sets `OPENAI_JUDGEMENT_MODEL`
- **THEN** it has no effect; the small tier keeps its own setting

### Requirement: Rate-limit resilience

Harvest judgement calls SHALL be throttled to at most 6 in flight, and retried up to 5 times with growing back-off when the provider rate-limits. Other errors SHALL surface immediately.

#### Scenario: Provider returns 429

- **WHEN** a judgement call is rate-limited
- **THEN** it is retried after 5, 10, 15 and 20 seconds before failing

### Requirement: Error reporting

When a Sentry DSN is configured, unhandled errors in a run SHALL be reported to Sentry.

#### Scenario: Crash with Sentry configured

- **WHEN** a run fails with an unhandled error and a DSN is set
- **THEN** the error is sent to Sentry

### Requirement: Token usage reporting

Every run that calls a model SHALL print, before it starts, the model of each tier, and at the end the input and output tokens used per model.

#### Scenario: Harvest run

- **WHEN** a harvest finishes
- **THEN** it prints `models: small=…, base=…, thinking=…` first and one `<model>: <n> tokens in, <m> out` line per model used at the end
