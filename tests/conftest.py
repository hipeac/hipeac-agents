"""Shared test fixtures for the vision-watch workspace tests."""

from pathlib import Path

import pytest

from hipeac_agents.agents.vision_watch import workspace


THEMES_YAML = """\
themes:
  - theme: next-computing-paradigm
    chapter: future-ahead
    definition: >
      The evolution toward distributed, on-demand computing across the
      compute continuum.
    keywords: [digital envelopes, compute continuum, personal AI]

  - theme: physical-ai
    chapter: technology-roadmap
    definition: >
      AI systems that directly interact with the physical world through
      sensors, actuators, and robotic systems.
    keywords: [embodied AI, robotics, humanoids, self-driving]

  - theme: agentic-ai
    chapter: technology-roadmap
    definition: >
      Autonomous AI systems acting as agents with delegated authority.
    keywords: [agents, MCP, A2A, agent communication protocols]
"""

SOURCE_CATALOG_YAML = """\
meta:
    version: 6
    company_slot_cap: 25

sources:
    - id: robot-report
      name: Robot Report
      url: "https://example.com/robot-report"
      feed_url: "https://example.com/robot-report/feed"
      class: aggregators
      themes: [physical-ai]
      region: global
      tier: 2
      independence: high
      stream: evidence

    - id: fabricated-knowledge
      name: Fabricated Knowledge
      url: "https://example.com/fk"
      class: capital
      themes: [new-hardware]
      region: global
      tier: 4
      independence: high
      stream: evidence
      newsletter: true

    - id: eu-fund
      name: EU Fund
      url: "https://example.com/eu"
      class: eu-uptake
      themes: [physical-ai]
      region: eu
      tier: 2
      independence: low
      stream: evidence

    - id: darpa-news
      name: DARPA News
      url: "https://example.com/darpa"
      class: programmes
      themes: [physical-ai, agentic-ai]
      region: global
      tier: 2
      independence: high
      stream: evidence

    - id: signals-watch
      name: Signals Watch
      url: "https://example.com/signals"
      class: foresight
      themes: []
      region: global
      tier: 3
      independence: med
      stream: signals
"""


@pytest.fixture
def data_dir(tmp_path: str) -> str:
    """A throwaway workspace root with the human-owned config files in place."""
    config = workspace.workspace_root(tmp_path) / "config"
    config.mkdir(parents=True)
    (config / "themes.yaml").write_text(THEMES_YAML, encoding="utf-8")
    (config / "source-catalog.yaml").write_text(SOURCE_CATALOG_YAML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def window() -> tuple[Path, Path] | tuple:
    """A fixed weekly window: Saturday 2026-06-06 through Friday 2026-06-12."""
    from datetime import date

    return date(2026, 6, 6), date(2026, 6, 12)
