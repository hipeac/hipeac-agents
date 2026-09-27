"""Shared test fixtures for the vision-watch workspace tests."""

from pathlib import Path

import pytest

from hipeac_agents.agents.vision_watch import workspace


THEMES_YAML = """\
themes:
  - theme: next-computing-paradigm
    description: Computing delivered on demand across a continuum of devices, edge and cloud.
    questions: ["Are personal AI orchestrators emerging?"]
    look_for: [edge orchestration, live migration]
    keywords: [digital envelopes, compute continuum, personal AI]

  - theme: physical-ai
    description: AI that senses and acts in the physical world through robots and machines.
    look_for: [humanoid deployments, VLA models]
    keywords: [embodied AI, robotics, humanoids, self-driving]

  - theme: agentic-ai
    description: AI systems acting as agents with delegated authority.
    keywords: [agents, MCP, A2A, agent communication protocols]
"""

SOURCE_CATALOG_YAML = """\
classes:
    aggregators: {independence: low}
    capital: {independence: high}
    eu-uptake: {independence: low}
    programmes: {independence: high}
    foresight: {independence: med}

sources:
    aggregators:
        - {id: robot-report, name: Robot Report, url: "https://example.com/robot-report",
           feed_url: "https://example.com/robot-report/feed", independence: high}
    capital:
        - {id: fabricated-knowledge, name: Fabricated Knowledge, url: "https://example.com/fk",
           senders: [fk@substack.com]}
    eu-uptake:
        - {id: eu-fund, name: EU Fund, url: "https://example.com/eu", region: eu}
    programmes:
        - {id: darpa-news, name: DARPA News, url: "https://example.com/darpa"}
    foresight:
        - {id: signals-watch, url: "https://example.com/signals"}
"""


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path_factory, monkeypatch):
    """Point the default workspace at a throwaway dir, never the ``.env`` one.

    ``./run`` loads ``.env``, whose data dir is the live workspace; a test that
    reads the default workspace (or a CLI run that rewrites it) must not reach it.
    """
    from hipeac_agents.agents.vision_watch import settings as watch_settings

    monkeypatch.setattr(watch_settings, "DATA_DIR", str(tmp_path_factory.mktemp("default-workspace")))


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
