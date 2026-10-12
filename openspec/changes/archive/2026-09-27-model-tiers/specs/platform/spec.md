## RENAMED Requirements

- FROM: `### Requirement: Two model roles`
- TO: `### Requirement: Model tiers`

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Token usage reporting

Every run that calls a model SHALL print, before it starts, the model of each tier, and at the end the input and output tokens used per model.

#### Scenario: Harvest run

- **WHEN** a harvest finishes
- **THEN** it prints `models: small=…, base=…, thinking=…` first and one `<model>: <n> tokens in, <m> out` line per model used at the end
