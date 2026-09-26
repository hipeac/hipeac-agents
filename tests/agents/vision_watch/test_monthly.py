"""Monthly digest node tests (LLM and mail faked)."""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.monthly import node as monthly_node_mod
from hipeac_agents.agents.vision_watch.nodes.monthly.models import MonthlyBottomLine, TrendProse
from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry
from hipeac_agents.agents.vision_watch.state import VisionWatchState
from hipeac_agents.services.factory import Services
from tests.agents.vision_watch._fakes import FakeLLM, FakeMail


@pytest.fixture(autouse=True)
def _setup(data_dir, monkeypatch):
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.DATA_DIR", data_dir)
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.HIPEAC_VISION_BOARD_EMAIL", "news@example.com")
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")
    workspace.append_cluster(
        Cluster(
            id="humanoid-deployment",
            name="Humanoids",
            opened="2026-W28",
            entries=[
                ClusterEntry(
                    week="2026-W28",
                    finding_id="f-2026-W28-01",
                    source_id="robot-report",
                    source_class="aggregators",
                    tier=2,
                    region="global",
                    date=date(2026, 7, 8),
                    note="Humanoids deployed in a warehouse.",
                    url="https://example.com/a",
                )
            ],
        ),
        theme="physical-ai",
        created=date(2026, 7, 10),
    )


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM(
        {
            TrendProse: TrendProse(
                trend_name="Humanoids at work",
                evidence_summary="One deployment.",
                why_it_matters="Labour.",
                confidence="low",
                likelihood="possible",
                europe="GAP: few EU vendors",
                recommendation="keep watching",
            ),
            MonthlyBottomLine: MonthlyBottomLine(text="Humanoids moved from demos to a first warehouse deployment."),
        }
    )


class TestMonthlySend:
    async def test_composed_month_is_sendable_later_exactly_once(self, llm):
        """Regression (baseline B1): a month composed without ``--send`` could
        never be sent — the recorded-digest replay returned before the send."""
        mail = FakeMail()
        services = Services(crawl=None, mail=mail, vision=None)

        await monthly_node_mod.monthly_node(
            VisionWatchState.model_construct(week="2026-W31", month="2026-07", send=False), services=services, llm=llm
        )
        assert not mail.sent
        llm.calls.clear()

        first = await monthly_node_mod.monthly_node(
            VisionWatchState.model_construct(week="2026-W31", month="2026-07", send=True), services=services, llm=llm
        )
        second = await monthly_node_mod.monthly_node(
            VisionWatchState.model_construct(week="2026-W31", month="2026-07", send=True), services=services, llm=llm
        )

        assert first["digest_sent"] is True
        assert second["digest_sent"] is False
        assert len(mail.sent) == 1
        assert mail.sent[0][2] == "Humanoids moved from demos to a first warehouse deployment."
        assert not llm.calls

    async def test_sending_is_opt_in(self, llm):
        mail = FakeMail()

        updates = await monthly_node_mod.monthly_node(
            VisionWatchState.model_construct(week="2026-W31", month="2026-07", send=False),
            services=Services(crawl=None, mail=mail, vision=None),
            llm=llm,
        )

        assert updates["digest_sent"] is False
        assert not mail.sent
        assert "## Bottom line" in updates["digest_markdown"]
