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

    def fake_build(nodes, services, models):
        builds.append((nodes, services, models))
        return FakeCompiled(nodes)

    monkeypatch.setattr("hipeac_agents.cli.graph.build_graph", fake_build)
    monkeypatch.setattr("hipeac_agents.cli._llm_configured", lambda: True)
    monkeypatch.setattr("hipeac_agents.cli.load_models", lambda: object())
    monkeypatch.setattr("hipeac_agents.cli.load_services_async", fake_services)
    return builds


class TestWeeklyHarvest:
    async def test_runs_harvest_then_source_health(self, fake_graph, capsys):
        exit_code = await cli.main(["weekly-harvest"])

        assert exit_code == 0
        assert fake_graph[0][0] == ["harvest", "health"]
        assert "robot-report: collected (1v/0r)" in capsys.readouterr().out


class TestWeeklyDigest:
    async def test_runs_cluster_then_digest(self, fake_graph):
        exit_code = await cli.main(["weekly-digest"])

        assert exit_code == 0
        assert fake_graph[0][0] == ["cluster", "digest"]


class TestInitialState:
    def test_state_carries_the_window(self):
        state = cli._initial_state("2026-W39", (date(2026, 9, 19), date(2026, 9, 25)))

        assert isinstance(state, VisionWatchState)
        assert state.week == "2026-W39"
        assert state.window_start == date(2026, 9, 19)
        assert state.window_end == date(2026, 9, 25)


def _freeze_today(monkeypatch, today: date) -> None:
    class FrozenDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr("hipeac_agents.cli.date", FrozenDate)


class TestTargetWindow:
    """Regression (baseline B2): a Sunday run harvested the week still open."""

    def test_saturday_run_targets_the_week_that_just_closed(self, monkeypatch):
        _freeze_today(monkeypatch, date(2026, 9, 26))

        assert cli._target_window() == (date(2026, 9, 19), date(2026, 9, 25))

    def test_friday_run_targets_its_own_week(self, monkeypatch):
        _freeze_today(monkeypatch, date(2026, 9, 25))

        assert cli._target_window() == (date(2026, 9, 19), date(2026, 9, 25))

    def test_on_date_targets_its_week(self, monkeypatch):
        _freeze_today(monkeypatch, date(2026, 9, 26))

        assert cli._target_window(date(2026, 6, 24)) == (date(2026, 6, 20), date(2026, 6, 26))

    def test_open_week_is_refused(self, monkeypatch):
        _freeze_today(monkeypatch, date(2026, 9, 26))

        with pytest.raises(ValueError, match="not yet"):
            cli._target_window(date(2026, 9, 27))

    async def test_cli_refuses_an_open_week(self, monkeypatch, fake_graph, capsys):
        _freeze_today(monkeypatch, date(2026, 9, 26))

        exit_code = await cli.main(["weekly-digest", "--on", "2026-09-28"])

        assert exit_code == 2
        assert fake_graph == []
        assert "refusing to run" in capsys.readouterr().err

    async def test_plain_harvest_state_carries_the_closed_week(self, monkeypatch, fake_graph):
        _freeze_today(monkeypatch, date(2026, 9, 27))
        compiled = []
        original = cli.graph.build_graph

        def capture(*args, **kwargs):
            built = original(*args, **kwargs)
            compiled.append(built)
            return built

        monkeypatch.setattr("hipeac_agents.cli.graph.build_graph", capture)

        await cli.main(["weekly-harvest"])

        state = compiled[0].invocations[0]
        assert state.week == "2026-W39"
        assert (state.window_start, state.window_end) == (date(2026, 9, 19), date(2026, 9, 25))


class TestWorkspaceOverride:
    """Regression (baseline B4): ``weekly-harvest`` ignored ``--data-dir``."""

    async def test_weekly_harvest_honours_data_dir(self, monkeypatch, fake_graph, tmp_path):
        from hipeac_agents.agents.vision_watch import settings as watch_settings

        monkeypatch.setattr(watch_settings, "DATA_DIR", "/nonexistent/configured")

        await cli.main(["weekly-harvest", "--data-dir", str(tmp_path)])

        assert str(tmp_path) == watch_settings.DATA_DIR


class RecordingCrawl:
    def __init__(self):
        self.scrapes = []

    async def scrape(self, url, fresh=False):
        self.scrapes.append(url)
        return None


class TestCrawlPreflight:
    """Regression (baseline B5): digest runs spent a crawl credit on a preflight."""

    async def test_digest_run_skips_the_crawl_preflight(self, monkeypatch, fake_graph):
        from hipeac_agents.services.factory import Services

        crawl = RecordingCrawl()

        async def services_with_crawl():
            return Services(crawl=crawl, mail=None, vision=None)

        monkeypatch.setattr("hipeac_agents.cli.load_services_async", services_with_crawl)

        await cli.main(["weekly-digest"])

        assert crawl.scrapes == []

    async def test_harvest_run_does_the_preflight(self, monkeypatch, fake_graph, tmp_path):
        from hipeac_agents.services.factory import Services

        crawl = RecordingCrawl()

        async def services_with_crawl():
            return Services(crawl=crawl, mail=None, vision=None)

        monkeypatch.setattr("hipeac_agents.cli.load_services_async", services_with_crawl)

        await cli.main(["weekly-harvest", "--data-dir", str(tmp_path)])

        assert crawl.scrapes == ["https://example.com"]


class TestRunSummary:
    """Regression (baseline B15): digest runs printed ``findings=0`` for a full week."""

    async def test_digest_summary_counts_the_recorded_week(self, monkeypatch, fake_graph, data_dir, capsys):
        from hipeac_agents.agents.vision_watch.schemas import Finding, FindingsFile, RejectedFile, RejectedItem

        _freeze_today(monkeypatch, date(2026, 6, 13))
        finding = Finding(
            id="f-2026-W24-01",
            date=date(2026, 6, 10),
            title="t",
            url="https://example.com/a",
            source_id="robot-report",
            region="global",
            tier=2,
            summary="s",
        )
        reject = RejectedItem(url="https://example.com/b", claimed_title="b", source_id="x", reason="off_theme")
        workspace.write_findings_file(
            FindingsFile(week="2026-W24", created=date(2026, 6, 13), findings=[finding]), data_dir
        )
        workspace.write_rejected_file(
            RejectedFile(week="2026-W24", created=date(2026, 6, 13), rejected=[reject, reject]), data_dir
        )

        await cli.main(["weekly-digest", "--data-dir", str(data_dir)])

        assert "week 2026-W24: findings=1 rejected=2" in capsys.readouterr().out


class TestRedo:
    async def test_digest_redo_sets_the_week_aside_before_running(self, monkeypatch, fake_graph, data_dir, capsys):
        _freeze_today(monkeypatch, date(2026, 6, 13))
        workspace.write_weekly_digest("2026-W24", "# old\n", data_dir)

        await cli.main(["weekly-digest", "--redo", "--data-dir", str(data_dir)])

        assert workspace.read_weekly_digest("2026-W24", data_dir) is None
        assert "set aside for a redo" in capsys.readouterr().out


class TestModelTiers:
    async def test_run_names_each_tier_and_reports_token_usage(self, fake_graph, monkeypatch, capsys):
        from contextlib import contextmanager
        from types import SimpleNamespace

        @contextmanager
        def fake_usage():
            yield SimpleNamespace(usage_metadata={"gpt-4o-mini": {"input_tokens": 1200, "output_tokens": 80}})

        monkeypatch.setattr("hipeac_agents.cli.get_usage_metadata_callback", fake_usage)
        from hipeac_agents.llms import Tier

        monkeypatch.setattr(
            "hipeac_agents.cli.tiers",
            lambda: {"small": Tier("gpt-6-luna", "none"), "base": Tier("gpt-6-sol", "low"), "thinking": Tier("m", "")},
        )

        await cli.main(["weekly-digest"])

        out = capsys.readouterr().out
        assert "models: small=gpt-6-luna (reasoning: none), base=gpt-6-sol (reasoning: low), thinking=m" in out
        assert "gpt-4o-mini: 1,200 tokens in, 80 out" in out
