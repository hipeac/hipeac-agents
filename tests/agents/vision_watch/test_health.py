"""Source-health tests: the judgement-free labels and the node's report and alert."""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.health import health_node, label_source
from hipeac_agents.agents.vision_watch.nodes.health.rules import QUIET, WeekActivity
from hipeac_agents.agents.vision_watch.schemas import (
    FindingsFile,
    HealthFile,
    RejectedFile,
    RejectedItem,
    SourceReport,
    SourcesFile,
)
from hipeac_agents.agents.vision_watch.state import VisionWatchState
from hipeac_agents.services.factory import Services
from tests.agents.vision_watch._fakes import FakeMail


STALE = WeekActivity(0, 5, frozenset({"out_of_window"}))


class TestLabels:
    @pytest.mark.parametrize(
        ("report", "expected"),
        [
            (SourceReport(source_id="s", status="blocked"), "skipped"),
            (SourceReport(source_id="s", status="failed"), "fetch_failed"),
            (SourceReport(source_id="s", status="collected", verified=1, flags=["feed_fetch_failed"]), "fetch_failed"),
            (SourceReport(source_id="s", status="collected", verified=1, flags=["feed_empty"]), "empty_feed"),
            (SourceReport(source_id="s", status="collected", verified=1, flags=["feed_truncated"]), "truncated_feed"),
            (SourceReport(source_id="s", status="collected", verified=2), "ok"),
        ],
    )
    def test_channel_observations(self, report, expected):
        assert label_source(report, [QUIET, QUIET]) == expected

    def test_three_weeks_of_only_out_of_window_is_a_stale_listing(self):
        report = SourceReport(source_id="s", status="collected", rejected=5, reasons={"out_of_window": 5})

        assert label_source(report, [STALE, STALE]) == "stale_listing"

    def test_one_in_window_week_breaks_the_streak(self):
        report = SourceReport(source_id="s", status="collected", rejected=5, reasons={"out_of_window": 5})

        assert label_source(report, [STALE, WeekActivity(1, 0, frozenset())]) == "ok"

    def test_three_empty_weeks_is_silent(self):
        assert label_source(SourceReport(source_id="s", status="empty"), [QUIET, QUIET]) == "silent"

    def test_streak_needs_enough_history(self):
        assert label_source(SourceReport(source_id="s", status="empty"), [QUIET]) == "ok"


@pytest.fixture
def workspace_dir(data_dir, monkeypatch):
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.DATA_DIR", data_dir)
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.HEALTH_ALERT_TO", "dev@example.com")
    return data_dir


def _harvested(week: str, reports: list[SourceReport]) -> None:
    created = date(2026, 9, 26)
    workspace.write_findings_file(FindingsFile(week=week, created=created, findings=[]))
    workspace.write_rejected_file(
        RejectedFile(
            week=week,
            created=created,
            rejected=[
                RejectedItem(
                    url=f"https://x/{week}/{r.source_id}",
                    claimed_title="old",
                    source_id=r.source_id,
                    reason="out_of_window",
                )
                for r in reports
                if r.rejected
            ],
        )
    )
    workspace.write_sources_file(SourcesFile(week=week, created=created, sources=reports))


class TestHealthNode:
    async def test_writes_the_report_and_alerts_on_first_problem(self, workspace_dir):
        _harvested("2026-W39", [SourceReport(source_id="robot-report", status="collected", flags=["feed_empty"])])
        mail = FakeMail()

        await health_node(
            VisionWatchState(week="2026-W39", send=True), services=Services(crawl=None, mail=mail, vision=None)
        )

        health = workspace.read_health_file("2026-W39")
        assert health.labels == {"robot-report": "empty_feed"}
        assert (workspace.week_dir("2026-W39") / "health.md").read_text().count("robot-report") == 1
        assert mail.sent[0][1] == "dev@example.com"
        assert "1 sources need attention" in mail.sent[0][2]

    async def test_no_alert_when_nothing_changed(self, workspace_dir):
        _harvested("2026-W38", [SourceReport(source_id="robot-report", status="collected", flags=["feed_empty"])])
        workspace.write_health(
            HealthFile(week="2026-W38", created=date(2026, 9, 19), labels={"robot-report": "empty_feed"}), "#"
        )
        _harvested("2026-W39", [SourceReport(source_id="robot-report", status="collected", flags=["feed_empty"])])
        mail = FakeMail()

        await health_node(
            VisionWatchState(week="2026-W39", send=True), services=Services(crawl=None, mail=mail, vision=None)
        )

        assert not mail.sent
        assert "unchanged" in (workspace.week_dir("2026-W39") / "health.md").read_text()

    async def test_alert_is_opt_in(self, workspace_dir):
        _harvested("2026-W39", [SourceReport(source_id="robot-report", status="failed")])
        mail = FakeMail()

        await health_node(VisionWatchState(week="2026-W39"), services=Services(crawl=None, mail=mail, vision=None))

        assert not mail.sent
        assert workspace.read_health_file("2026-W39").labels == {"robot-report": "fetch_failed"}

    async def test_stale_listing_uses_previous_weeks_evidence(self, workspace_dir):
        stale = SourceReport(source_id="eu-fund", status="collected", rejected=1, reasons={"out_of_window": 1})
        for week in ("2026-W37", "2026-W38", "2026-W39"):
            _harvested(week, [stale])

        await health_node(VisionWatchState(week="2026-W39"), services=Services(crawl=None, mail=None, vision=None))

        assert workspace.read_health_file("2026-W39").labels == {"eu-fund": "stale_listing"}

    async def test_non_catalog_channels_and_replays_are_ignored(self, workspace_dir):
        _harvested("2026-W39", [SourceReport(source_id="sweep", status="failed")])

        await health_node(VisionWatchState(week="2026-W39"), services=Services(crawl=None, mail=None, vision=None))
        second = await health_node(
            VisionWatchState(week="2026-W39"), services=Services(crawl=None, mail=None, vision=None)
        )

        assert workspace.read_health_file("2026-W39").labels == {}
        assert second == {}
