"""CLI entrypoint tests (services and LLM mocked, graph faked)."""

from datetime import date

import pytest

import hipeac_agents.cli as cli
from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.state import VisionWatchState


class FakeCompiled:
    def __init__(self, nodes):
        self.nodes = nodes
        self.invocations = []

    async def ainvoke(self, state):
        self.invocations.append(state)
        return {
            "findings": [],
            "rejected": [],
            "source_outcomes": [{"source_id": "robot-report", "status": "collected", "verified": 1, "rejected": 0}],
        }


@pytest.fixture
def fake_graph(monkeypatch):
    builds = []

    async def fake_services():
        from hipeac_agents.services.factory import Services

        return Services(crawl=None, mail=None, vision=None)

    def fake_build(nodes, services, judgement_llm, prose_llm=None):
        builds.append((nodes, services, judgement_llm, prose_llm))
        return FakeCompiled(nodes)

    monkeypatch.setattr("hipeac_agents.cli.graph.build_graph", fake_build)
    monkeypatch.setattr("hipeac_agents.cli._llm_configured", lambda: True)
    monkeypatch.setattr("hipeac_agents.cli._build_llms", lambda: (object(), object()))
    monkeypatch.setattr("hipeac_agents.cli.load_services_async", fake_services)
    return builds


class TestWeeklyHarvest:
    async def test_runs_harvest_node_only(self, fake_graph, capsys):
        exit_code = await cli.main(["weekly-harvest"])

        assert exit_code == 0
        assert fake_graph[0][0] == ["harvest"]
        assert "robot-report: collected (1v/0r)" in capsys.readouterr().out


class TestWeeklyDigest:
    async def test_runs_cluster_then_digest(self, fake_graph):
        exit_code = await cli.main(["weekly-digest"])

        assert exit_code == 0
        assert fake_graph[0][0] == ["cluster", "digest"]


class TestInitialState:
    def test_state_carries_current_window(self):
        state = cli._initial_state("2026-W24")

        assert isinstance(state, VisionWatchState)
        assert state.week == "2026-W24"
        assert state.window_start.weekday() == 5  # Saturday
        assert state.window_end.weekday() == 4  # Friday


class TestWeekLabel:
    def test_label_matches_closing_friday(self):
        today = date(2026, 9, 10)
        _window_start, window_end = workspace.current_window(today)

        assert cli._week_label(today) == workspace.weekly_label(window_end)
