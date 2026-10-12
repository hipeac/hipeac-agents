## MODIFIED Requirements

### Requirement: Themes

Each theme in `themes.yaml` SHALL be one of the Vision's broad lines: an id, an optional title readers see (the id when absent), a plain-words description, optional open questions the next Vision asks in it, what to look for (real-world names), optional keyword hints and a sweep query. Every judgement SHALL see all themes. Clusters are keyed by theme id, in file order. Each open question SHALL be addressed as `<theme id>.<n>`, n counting from 1 in file order.

#### Scenario: Unknown question id

- **WHEN** a verdict names a theme id not in `themes.yaml`
- **THEN** that id is ignored, and a candidate left with none is rejected `off_theme`

#### Scenario: Question ids

- **WHEN** the `agentic-ai` theme lists three questions
- **THEN** they are `agentic-ai.1`, `agentic-ai.2` and `agentic-ai.3`, in file order
