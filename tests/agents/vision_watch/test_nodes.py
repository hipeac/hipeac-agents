"""Node-level tests: harvest, cluster, digest, and the graph wiring.

MCP/service boundaries are always mocked (``_fakes.py``); storage runs
against a throwaway data directory. The LLM is scripted per judgement call.
"""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch import graph, workspace
from hipeac_agents.agents.vision_watch.nodes import cluster as cluster_node_mod
from hipeac_agents.agents.vision_watch.nodes import digest as digest_node_mod
from hipeac_agents.agents.vision_watch.nodes import harvest as harvest_node_mod
from hipeac_agents.agents.vision_watch.nodes.cluster import GroupingPlan
from hipeac_agents.agents.vision_watch.nodes.digest import DigestProse
from hipeac_agents.agents.vision_watch.nodes.harvest.models import (
    CandidateList,
    GateVerdict,
)
from hipeac_agents.services.factory import Services
from hipeac_agents.services.types import MailMessage
from tests.agents.vision_watch._fakes import (
    FakeCrawl,
    FakeLLM,
    FakeMail,
    make_candidate_handler,
    make_gate_handler,
    make_grouping_handler,
)


def _services(crawl=None, mail=None, vision=None) -> Services:
    return Services(crawl=crawl, mail=mail, vision=vision)


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


class TestHarvestNode:
    @pytest.fixture(autouse=True)
    def _setup(self, data_dir, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.DATA_DIR", data_dir)
        monkeypatch.setattr(
            "hipeac_agents.agents.vision_watch.nodes.harvest.channels.http_url_is_dead", lambda url: False
        )

    @pytest.fixture
    def weekly_catalog(self, data_dir):
        config = workspace.workspace_root(data_dir) / "config" / "source-catalog.yaml"
        config.write_text(
            "meta:\n"
            "    version: 1\n"
            "sources:\n"
            "    - id: robot-report\n"
            "      name: Robot Report\n"
            "      url: https://example.com/feed\n"
            "      class: aggregators\n"
            "      themes: [physical-ai]\n"
            "      region: global\n"
            "      tier: 2\n"
            "      independence: high\n"
            "      stream: evidence\n",
            encoding="utf-8",
        )

    async def test_collects_verified_finding(self, data_dir, llm, weekly_catalog):
        llm.handlers[CandidateList] = make_candidate_handler(
            [
                {
                    "title": "Humanoid deployed",
                    "url": "https://example.com/item",
                    "date": "2026-06-09",
                    "summary": "Deployment announced.",
                }
            ]
        )
        llm.handlers[GateVerdict] = make_gate_handler(["physical-ai"])
        crawl = FakeCrawl(
            pages={
                "https://example.com/feed": ("Feed", "# Feed\nHumanoid deployed — https://example.com/item"),
                "https://example.com/item": ("Humanoid deployed", "Full item text."),
            }
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        assert len(updates["findings"]) == 1
        assert updates["findings"][0].id == "f-2026-W24-01"
        assert updates["findings"][0].source_id == "robot-report"
        assert updates["source_outcomes"][0].status == "collected"
        assert (workspace.week_dir("2026-W24") / "findings.json").exists()
        report = workspace.read_sources_file("2026-W24")
        assert [(r.source_id, r.status, r.verified) for r in report.sources if r.source_id == "robot-report"] == [
            ("robot-report", "collected", 1)
        ]

    async def test_already_harvested_week_replays_instead_of_re_collecting(self, data_dir, llm, weekly_catalog):
        """Regression: the evidence files are write-once, so re-running a week
        used to scrape and judge everything again only to raise on the write."""
        from hipeac_agents.agents.vision_watch.schemas import Finding, FindingsFile, RejectedFile, RejectedItem
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        recorded = Finding.model_validate(
            {
                "id": "f-2026-W24-01",
                "date": "2026-06-09",
                "title": "Recorded",
                "url": "https://example.com/item",
                "source_id": "robot-report",
                "region": "global",
                "tier": 2,
                "theme_ids": ["physical-ai"],
                "summary": "Already on disk.",
            }
        )
        workspace.write_findings_file(FindingsFile(week="2026-W24", created=date(2026, 6, 12), findings=[recorded]))
        workspace.write_rejected_file(
            RejectedFile(
                week="2026-W24",
                created=date(2026, 6, 12),
                rejected=[
                    RejectedItem(url="https://example.com/no", claimed_title="No", source_id="s", reason="off_theme")
                ],
            )
        )
        crawl = FakeCrawl()
        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        assert [f.id for f in updates["findings"]] == ["f-2026-W24-01"]
        assert [r.url for r in updates["rejected"]] == ["https://example.com/no"]
        assert updates["source_outcomes"][0].status == "skipped"
        assert not llm.calls, "a recorded week must cost no LLM calls"
        assert not crawl.scrape_calls, "a recorded week must cost no scrapes"

    async def test_refuses_to_harvest_over_stale_cluster_entries(self, data_dir, llm, weekly_catalog):
        """Regression (baseline B3): finding ids are reused on a re-harvest, so
        entries left from the earlier harvest would point at other findings."""
        from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        workspace.append_cluster(
            Cluster(
                id="humanoid-deployment",
                name="Humanoids",
                opened="2026-W24",
                entries=[
                    ClusterEntry(
                        week="2026-W24",
                        finding_id="f-2026-W24-01",
                        source_id="robot-report",
                        source_class="aggregators",
                        tier=2,
                        region="global",
                        date=date(2026, 6, 9),
                        note="Old.",
                        url="https://example.com/old",
                    )
                ],
            ),
            theme="physical-ai",
            created=date(2026, 6, 12),
        )
        crawl = FakeCrawl()
        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        with pytest.raises(workspace.WorkspaceError, match="--redo"):
            await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        assert not crawl.scrape_calls
        assert not llm.calls

    async def test_unverifiable_url_rejected(self, data_dir, llm, weekly_catalog):
        llm.handlers[CandidateList] = make_candidate_handler(
            [
                {
                    "title": "Humanoid deployed",
                    "url": "https://example.com/404",
                    "date": "2026-06-09",
                    "summary": "Robotics milestone.",
                }
            ]
        )
        llm.handlers[GateVerdict] = make_gate_handler(["physical-ai"])
        crawl = FakeCrawl(pages={"https://example.com/feed": ("Feed", "link https://example.com/404")})
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        assert updates["findings"] == []
        assert updates["rejected"][0].reason == "url_404"

    async def test_title_mismatch_rejected(self, data_dir, llm, weekly_catalog):
        llm.handlers[CandidateList] = make_candidate_handler(
            [
                {
                    "title": "Humanoid deployed",
                    "url": "https://example.com/item",
                    "date": "2026-06-09",
                    "summary": "Robotics milestone.",
                }
            ]
        )
        llm.handlers[GateVerdict] = make_gate_handler(["physical-ai"], matches=False)
        crawl = FakeCrawl(
            pages={
                "https://example.com/feed": ("Feed", "link https://example.com/item"),
                "https://example.com/item": ("Something else entirely", "Body"),
            }
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        assert updates["rejected"][0].reason == "title_mismatch"

    async def test_off_theme_rejected(self, data_dir, llm, weekly_catalog):
        llm.handlers[CandidateList] = make_candidate_handler(
            [
                {
                    "title": "Celebrity gossip",
                    "url": "https://example.com/item",
                    "date": "2026-06-09",
                    "summary": "Nothing to do with themes.",
                }
            ]
        )
        llm.handlers[GateVerdict] = make_gate_handler([])
        crawl = FakeCrawl(
            pages={
                "https://example.com/feed": ("Feed", "link https://example.com/item"),
                "https://example.com/item": ("Celebrity gossip", "Gossip text."),
            }
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        assert updates["rejected"][0].reason == "off_theme"

    async def test_newsletter_channel(self, data_dir, llm, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")
        config = workspace.workspace_root(data_dir) / "config" / "source-catalog.yaml"
        config.write_text(
            "meta:\n"
            "    version: 1\n"
            "sources:\n"
            "    - id: newsletter-source\n"
            "      name: Newsletter Source\n"
            "      url: https://example.com/site\n"
            "      class: aggregators\n"
            "      themes: [physical-ai]\n"
            "      region: global\n"
            "      tier: 2\n"
            "      independence: high\n"
            "      web: false\n"
            "      senders: [newsletter@substack.com]\n",
            encoding="utf-8",
        )

        from datetime import UTC, datetime

        message = MailMessage(
            inbox_id="vision-news",
            message_id="m1",
            from_="newsletter@substack.com",
            subject="Weekly",
            timestamp=datetime(2026, 6, 10, 8, tzinfo=UTC),
        )
        body = "This week: Humanoid deployed https://example.com/item — full story inside."
        llm.handlers[CandidateList] = make_candidate_handler(
            [{"title": "Humanoid deployed", "url": "https://example.com/item", "date": "", "summary": "s"}]
        )
        llm.handlers[GateVerdict] = make_gate_handler(["physical-ai"])
        crawl = FakeCrawl(
            pages={
                "https://example.com/item": ("Humanoid deployed", "Full item text."),
            }
        )
        mail = FakeMail(messages=[message], bodies={"m1": body})
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl, mail), llm=llm)

        newsletter = [f for f in updates["findings"] if f.access_method == "newsletter"]
        assert [f.source_id for f in newsletter] == ["newsletter-source"]
        assert newsletter[0].date == date(2026, 6, 10), "an undated newsletter item takes its message date"

    async def test_crawl_missing_fails_all_due_sources(self, data_dir, llm, weekly_catalog):
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(None), llm=llm)

        assert updates["source_outcomes"][0].status == "failed"

    async def test_sweep_channel(self, data_dir, llm, weekly_catalog):
        from hipeac_agents.agents.vision_watch.state import VisionWatchState
        from hipeac_agents.services.types import SearchHit

        llm.handlers[CandidateList] = make_candidate_handler(
            [{"title": "Humanoid deployed", "url": "", "date": "2026-06-09", "summary": "Deployment announced."}]
        )
        llm.handlers[GateVerdict] = make_gate_handler(["physical-ai"])
        crawl = FakeCrawl(
            pages={"https://example.com/sweep-hit": ("Humanoids industrial deployment", "Full sweep item text.")},
            search_hits=[
                SearchHit(
                    url="https://example.com/sweep-hit",
                    title="Humanoids industrial deployment",
                    description="robotics deployment",
                )
            ],
        )

        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        sweep_outcomes = [o for o in updates["source_outcomes"] if getattr(o, "source_id", None) == "sweep"]
        assert sweep_outcomes and sweep_outcomes[0].status == "collected"
        assert any(f.access_method == "sweep" and f.source_id == "sweep" for f in updates["findings"])
        assert any("physical-ai" in f.theme_ids for f in updates["findings"])
        # Regression (baseline B13): the search is bounded to the harvested
        # window, not to a literal "past week" that breaks backfills.
        assert crawl.search_ranges and set(crawl.search_ranges) == {(date(2026, 6, 6), date(2026, 6, 12))}
        assert not any("past week" in q for q in crawl.search_calls)

    async def test_channel_error_is_reported_under_its_source(self, data_dir, llm, weekly_catalog):
        """Regression (baseline B11): a raising channel was reported as ``unknown``."""
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        class RaisingCrawl(FakeCrawl):
            async def scrape(self, url, fresh=False):
                if url == "https://example.com/feed":
                    raise RuntimeError("boom")
                return await super().scrape(url, fresh)

        state = VisionWatchState.model_construct(
            week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12), skip_sweep=True
        )

        updates = await harvest_node_mod.harvest_node(state, services=_services(RaisingCrawl()), llm=llm)

        outcome = next(o for o in updates["source_outcomes"] if o.source_id == "robot-report")
        assert outcome.status == "failed"
        assert "boom" in outcome.detail
        assert not any(o.source_id == "unknown" for o in updates["source_outcomes"])

    async def test_page_source_with_only_rejects_is_collected(self, data_dir, llm, weekly_catalog):
        """Regression (baseline B22): a page source whose candidates were all
        rejected read as ``empty``, like a source that yielded nothing."""
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        llm.handlers[CandidateList] = make_candidate_handler(
            [{"title": "Old news", "url": "https://example.com/old", "date": "2026-01-01", "summary": "s"}]
        )
        crawl = FakeCrawl(pages={"https://example.com/feed": ("Feed", "Old news — https://example.com/old")})
        state = VisionWatchState.model_construct(
            week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12), skip_sweep=True
        )

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        outcome = next(o for o in updates["source_outcomes"] if o.source_id == "robot-report")
        assert (outcome.status, outcome.rejected) == ("collected", 1)


class TestClusterNode:
    @pytest.fixture(autouse=True)
    def _setup(self, data_dir, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.DATA_DIR", data_dir)
        monkeypatch.setattr(
            "hipeac_agents.agents.vision_watch.nodes.harvest.channels.http_url_is_dead", lambda url: False
        )

    @pytest.fixture
    def finding(self):
        from hipeac_agents.agents.vision_watch.schemas import Finding

        return Finding.model_validate(
            {
                "id": "f-2026-W24-01",
                "date": "2026-06-09",
                "title": "Humanoid deployed",
                "url": "https://example.com/a",
                "source_id": "robot-report",
                "region": "global",
                "tier": 2,
                "theme_ids": ["physical-ai"],
                "summary": "Deployment announced.",
            }
        )

    def _write_findings(self, finding) -> None:
        from hipeac_agents.agents.vision_watch.schemas import FindingsFile

        workspace.write_findings_file(FindingsFile(week="2026-W24", created=date(2026, 6, 11), findings=[finding]))

    async def test_opens_cluster_and_appends_entries(self, llm, finding):
        finding = {
            "id": "f-2026-W24-01",
            "date": "2026-06-09",
            "title": "Humanoid deployed",
            "url": "https://example.com/a",
            "source_id": "robot-report",
            "region": "global",
            "tier": 2,
            "theme_ids": ["physical-ai"],
            "summary": "Deployment announced.",
        }
        llm.handlers[GroupingPlan] = make_grouping_handler(
            [
                {
                    "finding_id": "f-2026-W24-01",
                    "new_cluster": {
                        "id": "humanoid-deployment",
                        "name": "Humanoids in industry",
                        "theme": "physical-ai",
                    },
                    "note": "First entry.",
                }
            ]
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        self._write_findings(finding)
        state = VisionWatchState(week="2026-W24")

        await cluster_node_mod.cluster_node(state, services=Services(crawl=None, mail=None, vision=None), llm=llm)

        log = workspace.read_cluster_log("physical-ai")
        assert log is not None and len(log.clusters) == 1
        assert log.clusters[0].id == "humanoid-deployment"
        assert log.clusters[0].entries[0].finding_id == "f-2026-W24-01"

    async def test_assignment_to_unknown_cluster_is_reported_unmatched(self, llm, finding):
        """Regression (baseline B14): a grouping that named a cluster id that
        does not exist dropped the finding silently, counted as assigned."""
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        llm.handlers[GroupingPlan] = make_grouping_handler(
            [{"finding_id": "f-2026-W24-01", "extends_cluster_id": "no-such-cluster"}]
        )
        self._write_findings(finding)

        updates = await cluster_node_mod.cluster_node(
            VisionWatchState(week="2026-W24"), services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        assert any("f-2026-W24-01" in note for note in updates["notes"])

    async def test_rerunning_the_same_week_is_a_no_op(self, llm, finding):
        """Re-running a week must recover from 'cluster exists' and 'entry
        already recorded' — and from nothing else. Recovery keys off exception
        type now, not off the wording of the error message."""
        finding = {
            "id": "f-2026-W24-01",
            "date": "2026-06-09",
            "title": "Humanoid deployed",
            "url": "https://example.com/a",
            "source_id": "robot-report",
            "region": "global",
            "tier": 2,
            "theme_ids": ["physical-ai"],
            "summary": "Deployment announced.",
        }
        llm.handlers[GroupingPlan] = make_grouping_handler(
            [
                {
                    "finding_id": "f-2026-W24-01",
                    "new_cluster": {
                        "id": "humanoid-deployment",
                        "name": "Humanoids in industry",
                        "theme": "physical-ai",
                    },
                    "note": "First entry.",
                }
            ]
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        self._write_findings(finding)
        state = VisionWatchState(week="2026-W24")
        services = Services(crawl=None, mail=None, vision=None)

        await cluster_node_mod.cluster_node(state, services=services, llm=llm)
        await cluster_node_mod.cluster_node(state, services=services, llm=llm)

        log = workspace.read_cluster_log("physical-ai")
        assert len(log.clusters) == 1
        assert [e.finding_id for e in log.clusters[0].entries] == ["f-2026-W24-01"]

    async def test_unexpected_workspace_error_is_not_swallowed(self, llm, finding, monkeypatch):
        """A real append-only violation must surface, not be mistaken for a
        re-run: only the two recoverable types are caught."""
        from hipeac_agents.agents.vision_watch.state import VisionWatchState
        from hipeac_agents.storage import WorkspaceError

        finding = {
            "id": "f-2026-W24-01",
            "date": "2026-06-09",
            "title": "Humanoid deployed",
            "url": "https://example.com/a",
            "source_id": "robot-report",
            "region": "global",
            "tier": 2,
            "theme_ids": ["physical-ai"],
            "summary": "Deployment announced.",
        }
        llm.handlers[GroupingPlan] = make_grouping_handler(
            [
                {
                    "finding_id": "f-2026-W24-01",
                    "new_cluster": {
                        "id": "humanoid-deployment",
                        "name": "Humanoids in industry",
                        "theme": "physical-ai",
                    },
                    "note": "First entry.",
                }
            ]
        )

        def boom(*args, **kwargs):
            raise WorkspaceError("disk is on fire")

        monkeypatch.setattr(workspace, "append_cluster", boom)
        self._write_findings(finding)

        with pytest.raises(WorkspaceError, match="disk is on fire"):
            await cluster_node_mod.cluster_node(
                VisionWatchState(week="2026-W24"),
                services=Services(crawl=None, mail=None, vision=None),
                llm=llm,
            )

    async def test_reads_findings_file_not_state(self, llm, finding):
        """Regression: a digest run carries no findings in state; the cluster
        node must read the week's findings file, or the digest comes out empty."""
        self._write_findings(finding)
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState(week="2026-W24")  # findings empty, as in weekly-digest
        llm.handlers[GroupingPlan] = make_grouping_handler(
            [
                {
                    "finding_id": "f-2026-W24-01",
                    "new_cluster": {
                        "id": "humanoid-deployment",
                        "name": "Humanoids in industry",
                        "theme": "physical-ai",
                    },
                    "note": "First entry.",
                }
            ]
        )

        await cluster_node_mod.cluster_node(state, services=Services(crawl=None, mail=None, vision=None), llm=llm)

        log = workspace.read_cluster_log("physical-ai")
        assert log is not None and len(log.clusters) == 1

    async def test_append_only_never_rewrites(self, llm):
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry, Finding

        workspace.append_cluster(
            Cluster(
                id="existing",
                name="Existing",
                opened="2026-W23",
                entries=[
                    ClusterEntry.model_validate(
                        {
                            "week": "2026-W23",
                            "finding_id": "f-old",
                            "source_id": "robot-report",
                            "source_class": "aggregators",
                            "tier": 2,
                            "region": "global",
                            "date": "2026-06-05",
                            "note": "n",
                            "url": "u",
                        }
                    )
                ],
            ),
            theme="physical-ai",
            created=date_cls(2026, 1, 8),
        )
        finding = Finding.model_validate(
            {
                "id": "f-2026-W24-01",
                "date": "2026-06-09",
                "title": "Humanoid deployed",
                "url": "https://example.com/a",
                "source_id": "robot-report",
                "region": "global",
                "tier": 2,
                "theme_ids": ["physical-ai"],
                "summary": "Deployment announced.",
            }
        )
        llm.handlers[GroupingPlan] = make_grouping_handler(
            [{"finding_id": "f-2026-W24-01", "extends_cluster_id": "existing", "note": "Extends."}]
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState(week="2026-W24")
        self._write_findings(finding)

        await cluster_node_mod.cluster_node(state, services=Services(crawl=None, mail=None, vision=None), llm=llm)

        log = workspace.read_cluster_log("physical-ai")
        assert [e.finding_id for e in log.clusters[0].entries] == ["f-old", "f-2026-W24-01"]

    async def test_unmatched_findings_reported(self, llm, finding):
        llm.handlers[GroupingPlan] = make_grouping_handler([])  # grouping call places nothing
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState(week="2026-W24")
        self._write_findings(finding)

        updates = await cluster_node_mod.cluster_node(
            state, services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        assert updates["notes"] and "joined no cluster" in updates["notes"][0]


class TestDigestNode:
    @pytest.fixture(autouse=True)
    def _setup(self, data_dir, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.DATA_DIR", data_dir)
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry

        workspace.append_cluster(
            Cluster(
                id="humanoid-deployment",
                name="Humanoids",
                opened="2026-W24",
                entries=[
                    ClusterEntry.model_validate(
                        {
                            "week": "2026-W24",
                            "finding_id": "f-1",
                            "source_id": "robot-report",
                            "source_class": "aggregators",
                            "tier": 2,
                            "region": "global",
                            "date": "2026-06-09",
                            "note": "Deployment",
                            "url": "https://example.com/a",
                        }
                    )
                ],
            ),
            theme="physical-ai",
            created=date_cls(2026, 1, 8),
        )

    async def test_writes_and_sends_digest(self, llm, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.HIPEAC_VISION_BOARD_EMAIL", "news@example.com")
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")

        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {
                "lead": "Humanoids deployed.",
                "why_it_matters": "Field shifts.",
                "europe": "GAP: none",
                "maturity": "watch, low",
            }
        )
        mail = FakeMail()
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState.model_construct(week="2026-W24", send=True)

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=mail, vision=None), llm=llm
        )

        assert "## In brief" in updates["digest_markdown"]
        assert "## One big thing" in updates["digest_markdown"]
        assert "https://example.com/a" in updates["digest_markdown"]
        assert updates["digest_sent"] is True
        assert mail.sent[0][1] == "news@example.com"
        digest_path = workspace.weekly_digest_dir() / "digest-2026-W24.md"
        assert digest_path.exists()

    async def test_sends_markdown_and_html_parts(self, llm, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.HIPEAC_VISION_BOARD_EMAIL", "news@example.com")
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")
        monkeypatch.setattr(
            "hipeac_agents.agents.vision_watch.settings.HIPEAC_VISION_REPLY_TO", "webmaster@example.com"
        )

        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {
                "lead": "Humanoids deployed.",
                "why_it_matters": "Field shifts.",
                "europe": "GAP: none",
                "maturity": "watch, low",
            }
        )
        mail = FakeMail()
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        await digest_node_mod.digest_node(
            VisionWatchState.model_construct(week="2026-W24", send=True),
            services=Services(crawl=None, mail=mail, vision=None),
            llm=llm,
        )

        _, _, _, text, html, reply_to = mail.sent[0]
        assert reply_to == "webmaster@example.com"
        assert text.startswith("# HiPEAC Vision Watch")
        assert "## One big thing" in text
        # The HTML part carries rendered markup, not the raw markdown source.
        assert "<h2>One big thing</h2>" in html
        assert "## One big thing" not in html
        assert '<a href="https://example.com/a">' in html

    async def test_skips_send_without_mail_service(self, llm):
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        state = VisionWatchState.model_construct(week="2026-W24")

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        assert updates["digest_sent"] is False
        assert "## In brief" in updates["digest_markdown"]

    async def test_sending_is_opt_in(self, llm, monkeypatch):
        """Sending is opt-in: a fully configured run that omits ``send`` writes
        the digest and mails no one. The board list is the real audience."""
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.HIPEAC_VISION_BOARD_EMAIL", "news@example.com")
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        mail = FakeMail()
        state = VisionWatchState.model_construct(week="2026-W24")

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=mail, vision=None), llm=llm
        )

        assert updates["digest_sent"] is False
        assert not mail.sent
        assert (workspace.weekly_digest_dir() / "digest-2026-W24.md").exists()

    async def test_already_sent_week_is_not_recomposed_or_resent(self, llm, monkeypatch):
        """Regression: the digest is write-once, so a re-run used to pay for
        every prose call and then raise on the write. It now replays, and a
        digest already sent is never sent again."""
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.HIPEAC_VISION_BOARD_EMAIL", "news@example.com")
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        workspace.write_weekly_digest("2026-W24", "# Already composed\n")
        workspace.mark_weekly_digest_sent("2026-W24", "m-earlier")
        mail = FakeMail()
        llm.calls.clear()

        updates = await digest_node_mod.digest_node(
            VisionWatchState.model_construct(week="2026-W24", send=True),
            services=Services(crawl=None, mail=mail, vision=None),
            llm=llm,
        )

        assert updates["digest_markdown"] == "# Already composed\n"
        assert updates["digest_sent"] is False
        assert not mail.sent
        assert not llm.calls, "a recorded week must cost no LLM calls"

    async def test_composed_digest_is_sendable_later_exactly_once(self, llm, monkeypatch):
        """Regression (baseline B1): with sending opt-in, compose → review →
        ``--send`` silently mailed no one, because the recorded-digest replay
        returned before the send step."""
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.HIPEAC_VISION_BOARD_EMAIL", "news@example.com")
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        mail = FakeMail()
        services = Services(crawl=None, mail=mail, vision=None)

        composed = await digest_node_mod.digest_node(
            VisionWatchState.model_construct(week="2026-W24", send=False), services=services, llm=llm
        )
        assert not mail.sent
        llm.calls.clear()

        sent = await digest_node_mod.digest_node(
            VisionWatchState.model_construct(week="2026-W24", send=True), services=services, llm=llm
        )
        again = await digest_node_mod.digest_node(
            VisionWatchState.model_construct(week="2026-W24", send=True), services=services, llm=llm
        )

        assert sent["digest_sent"] is True
        assert again["digest_sent"] is False
        assert len(mail.sent) == 1
        assert mail.sent[0][3] == composed["digest_markdown"]
        assert mail.sent[0][2] == "HiPEAC Vision Watch — Week 2026-W24: Humanoids"
        assert not llm.calls, "sending a recorded digest must cost no LLM calls"
        assert workspace.weekly_digest_sent("2026-W24")

    async def test_lead_prefers_this_weeks_tier_over_lifetime_volume(self, llm):
        """Regression: the lead used to be picked by lifetime entry count, so a
        cluster with 30 old tier-3 entries always beat a fresh tier-1 burst."""
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry

        def make_entry(week: str, finding_id: str, tier: int, url: str) -> ClusterEntry:
            return ClusterEntry.model_validate(
                {
                    "week": week,
                    "finding_id": finding_id,
                    "source_id": "darpa-news",
                    "source_class": "programmes",
                    "tier": tier,
                    "region": "global",
                    "date": "2026-06-09",
                    "note": "n",
                    "url": url,
                }
            )

        heavy_entries = [
            make_entry(f"2026-W{(i % 20) + 1:02d}", f"h-{i}", 3, "https://example.com/heavy") for i in range(29)
        ] + [make_entry("2026-W24", "h-29", 3, "https://example.com/heavy")]
        workspace.append_cluster(
            Cluster(id="old-news", name="Old News", opened="2026-W01", entries=heavy_entries),
            theme="agentic-ai",
            created=date_cls(2026, 1, 8),
        )
        fresh_entries = [
            make_entry("2026-W24", "f-1", 1, "https://example.com/fresh-1"),
            make_entry("2026-W24", "f-2", 1, "https://example.com/fresh-2"),
        ]
        workspace.append_cluster(
            Cluster(id="fresh-news", name="Fresh News", opened="2026-W24", entries=fresh_entries),
            theme="agentic-ai",
            created=date_cls(2026, 1, 8),
        )
        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState.model_construct(week="2026-W24")

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        one_big_thing = (
            updates["digest_markdown"].split("## One big thing")[1].split("## What moved on each question")[0]
        )
        assert "https://example.com/fresh-1" in one_big_thing
        assert "https://example.com/heavy" not in one_big_thing

    async def test_tally_scoped_to_week_not_future_entries(self, llm):
        """Regression: the tally used to include entries logged after the
        digest's week, so a later re-composition of the same week disagreed."""
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry

        def make_entry(week: str, finding_id: str) -> ClusterEntry:
            return ClusterEntry.model_validate(
                {
                    "week": week,
                    "finding_id": finding_id,
                    "source_id": "darpa-news",
                    "source_class": "programmes",
                    "tier": 2,
                    "region": "global",
                    "date": "2026-06-09",
                    "note": "n",
                    "url": f"https://example.com/{finding_id}",
                }
            )

        workspace.append_cluster(
            Cluster(
                id="scoped-cluster",
                name="Scoped Cluster",
                opened="2026-W24",
                entries=[make_entry("2026-W24", "s-1"), make_entry("2026-W25", "s-2")],
            ),
            theme="agentic-ai",
            created=date_cls(2026, 1, 8),
        )
        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState.model_construct(week="2026-W24")

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        trending = updates["digest_markdown"].split("## Trending this week")[1]
        scoped_line = next(line for line in trending.splitlines() if "scoped-cluster" in line)
        assert "1 finding" in scoped_line
        assert "2 findings" not in scoped_line

    async def test_one_big_thing_source_is_strongest_entry_not_first_logged(self, llm):
        """Regression: the source line used to be the first this-week entry in
        log order, not the strongest one."""
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry

        def make_entry(finding_id: str, tier: int, url: str) -> ClusterEntry:
            return ClusterEntry.model_validate(
                {
                    "week": "2026-W24",
                    "finding_id": finding_id,
                    "source_id": "darpa-news",
                    "source_class": "programmes",
                    "tier": tier,
                    "region": "global",
                    "date": "2026-06-09",
                    "note": "n",
                    "url": url,
                }
            )

        workspace.append_cluster(
            Cluster(
                id="mixed-tier",
                name="Mixed Tier",
                opened="2026-W24",
                entries=[
                    make_entry("m-1", 3, "https://example.com/weak-first"),
                    make_entry("m-2", 1, "https://example.com/strong-second"),
                ],
            ),
            theme="agentic-ai",
            created=date_cls(2026, 1, 8),
        )
        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState.model_construct(week="2026-W24")

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        one_big_thing = (
            updates["digest_markdown"].split("## One big thing")[1].split("## What moved on each question")[0]
        )
        assert "https://example.com/strong-second" in one_big_thing
        assert "https://example.com/weak-first" not in one_big_thing

    async def test_exactly_one_digest_prose_call_per_run(self, llm):
        """Regression: prose used to be generated for every touched cluster,
        even though only the lead's prose is ever rendered."""
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry

        entry = ClusterEntry.model_validate(
            {
                "week": "2026-W24",
                "finding_id": "sc-1",
                "source_id": "darpa-news",
                "source_class": "programmes",
                "tier": 2,
                "region": "global",
                "date": "2026-06-09",
                "note": "n",
                "url": "https://example.com/sc-1",
            }
        )
        workspace.append_cluster(
            Cluster(id="second-cluster", name="Second Cluster", opened="2026-W24", entries=[entry]),
            theme="agentic-ai",
            created=date_cls(2026, 1, 8),
        )
        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState.model_construct(week="2026-W24")

        await digest_node_mod.digest_node(state, services=Services(crawl=None, mail=None, vision=None), llm=llm)

        prose_calls = [call for call in llm.calls if call[0] is DigestProse]
        assert len(prose_calls) == 1

    async def test_brewing_section_and_question_headings(self, llm):
        """The digest leads with what is brewing: long-horizon items and weak
        signals from foresight sources, and each theme shows its question."""
        from hipeac_agents.agents.vision_watch.schemas import Finding, FindingsFile
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        def finding(n: int, **extra) -> Finding:
            base = {
                "id": f"f-2026-W24-0{n}",
                "date": date(2026, 6, 9),
                "title": f"T{n}",
                "url": f"https://example.com/b{n}",
                "source_id": "darpa-news",
                "region": "global",
                "tier": 3,
                "summary": f"Summary {n}.",
            }
            return Finding(**{**base, **extra})

        workspace.write_findings_file(
            FindingsFile(
                week="2026-W24",
                created=date(2026, 6, 13),
                findings=[
                    finding(1, horizon="3-5y", significance=4, forward_note="Could reset EU fab plans."),
                    finding(2, horizon="now"),
                    finding(3, source_id="signals-watch", horizon="1-2y"),
                ],
            )
        )
        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )

        updates = await digest_node_mod.digest_node(
            VisionWatchState.model_construct(week="2026-W24"),
            services=Services(crawl=None, mail=None, vision=None),
            llm=llm,
        )

        markdown = updates["digest_markdown"]
        brewing = markdown.split("## What's brewing")[1].split("## What moved on each question")[0]
        assert "Summary 1. Could reset EU fab plans." in brewing
        assert "(3-5y)" in brewing
        assert "Summary 3." in brewing, "foresight sources are weak signals"
        assert "Summary 2." not in brewing
        assert "### physical-ai — Are AI agents entering the physical world safely?" in markdown

    async def test_finding_in_two_clusters_lists_both_once(self, llm):
        """Regression: a finding assigned to two clusters in the same theme
        used to print as two separate lines, one per cluster."""
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry

        def shared_entry(finding_id: str = "shared-1") -> ClusterEntry:
            return ClusterEntry.model_validate(
                {
                    "week": "2026-W24",
                    "finding_id": finding_id,
                    "source_id": "darpa-news",
                    "source_class": "programmes",
                    "tier": 2,
                    "region": "global",
                    "date": "2026-06-09",
                    "note": "Shared finding",
                    "url": "https://example.com/shared",
                }
            )

        workspace.append_cluster(
            Cluster(id="cluster-a", name="Cluster A", opened="2026-W24", entries=[shared_entry()]),
            theme="physical-ai",
            created=date_cls(2026, 1, 8),
        )
        workspace.append_cluster(
            Cluster(id="cluster-b", name="Cluster B", opened="2026-W24", entries=[shared_entry()]),
            theme="physical-ai",
            created=date_cls(2026, 1, 8),
        )
        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState.model_construct(week="2026-W24")

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        across = updates["digest_markdown"].split("## What moved on each question")[1].split("## Trending this week")[0]
        shared_lines = [line for line in across.splitlines() if "https://example.com/shared" in line]
        assert len(shared_lines) == 1
        assert "in cluster-a, cluster-b" in shared_lines[0]
        # No board tips recorded this week: no tips section either.
        assert "## Board tips this week" not in updates["digest_markdown"]

    async def test_theme_section_caps_entry_lines(self, llm):
        """A high-volume week must not print every entry: strongest first,
        capped, with the overflow counted."""
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry

        def entry(n: int) -> ClusterEntry:
            return ClusterEntry.model_validate(
                {
                    "week": "2026-W24",
                    "finding_id": f"f-{n:02d}",
                    "source_id": "darpa-news",
                    "source_class": "programmes",
                    "tier": (n % 4) + 1,
                    "region": "global",
                    "date": f"2026-06-{9 - (n % 9):02d}",
                    "note": f"Entry {n}",
                    "url": f"https://example.com/{n}",
                }
            )

        workspace.append_cluster(
            Cluster(id="cluster-a", name="Cluster A", opened="2026-W24", entries=[entry(n) for n in range(14)]),
            theme="agentic-ai",
            created=date_cls(2026, 1, 8),
        )
        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        state = VisionWatchState.model_construct(week="2026-W24")

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        across = updates["digest_markdown"].split("## What moved on each question")[1].split("## Trending this week")[0]
        item_lines = [line for line in across.splitlines() if line.startswith("- _Entry")]
        overflow = [line for line in across.splitlines() if "more entries this week" in line]
        assert len(item_lines) == 12
        assert overflow == ["- (+2 more entries this week — see the theme's cluster log.)"]
        # Strongest tier first, newest first within the tier: entry 0 is the
        # only tier-1 entry dated 2026-06-09.
        assert item_lines[0] == "- _Entry 0_ — [example.com](https://example.com/0) — in cluster-a"

    async def test_board_tips_render_in_own_section_even_unclustered(self, llm):
        """A board tip is editor-flagged: it must stay visible in the digest
        even when the grouping call left it in no cluster at all."""
        from hipeac_agents.agents.vision_watch.schemas import Finding, FindingsFile
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        workspace.write_findings_file(
            FindingsFile(
                week="2026-W24",
                created=date(2026, 6, 13),
                findings=[
                    Finding(
                        id="f-2026-W24-01",
                        date=date(2026, 6, 12),
                        title="LLMs as a cognitive virus",
                        url="https://arxiv.org/html/2609.03344v1",
                        source_id="board-tip",
                        region="global",
                        tier=4,
                        theme_ids=["agentic-society"],
                        datapoint="",
                        summary="An essay frames LLMs as a cognitive virus. [flagged by Test Sender]",
                        significance=2,
                        access_method="board-tip",
                    )
                ],
            )
        )
        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )

        updates = await digest_node_mod.digest_node(
            VisionWatchState.model_construct(week="2026-W24"),
            services=Services(crawl=None, mail=None, vision=None),
            llm=llm,
        )

        tips = updates["digest_markdown"].split("## Board tips this week")[1].split("## What moved on each question")[0]
        assert "LLMs as a cognitive virus" in tips
        assert "https://arxiv.org/html/2609.03344v1" in tips
        assert "flagged by Test Sender" in tips

    async def test_off_theme_rejects_render_as_signal_group(self, llm):
        from hipeac_agents.agents.vision_watch.nodes.digest import SignalGroups
        from hipeac_agents.agents.vision_watch.schemas import RejectedFile, RejectedItem
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        workspace.write_rejected_file(
            RejectedFile(
                week="2026-W24",
                created=date(2026, 6, 12),
                rejected=[
                    RejectedItem(
                        url="https://example.com/chips-act",
                        claimed_title="Chips Act 2.0 hits right notes",
                        source_id="science-business",
                        reason="off_theme",
                        summary="EU debates the budget behind its next chip subsidy round.",
                    ),
                    RejectedItem(
                        url="https://example.com/korea-fab",
                        claimed_title="S. Korea goes All In on AI",
                        source_id="chinatalk",
                        reason="off_theme",
                        summary="Korea and Germany both announce new chip fab investment.",
                    ),
                ],
            )
        )
        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        llm.handlers[SignalGroups] = lambda prompt: SignalGroups.model_validate(
            {
                "groups": [
                    {
                        "blurb": "EU and Asian states are racing on chip sovereignty.",
                        "urls": ["https://example.com/chips-act", "https://example.com/korea-fab"],
                    }
                ]
            }
        )
        state = VisionWatchState.model_construct(week="2026-W24")

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        assert "## Also worth watching" in updates["digest_markdown"]
        signals = updates["digest_markdown"].split("## Also worth watching")[1]
        assert "EU and Asian states are racing on chip sovereignty." in signals
        assert "https://example.com/chips-act" in signals
        assert "https://example.com/korea-fab" in signals

    async def test_no_signal_call_without_off_theme_rejects(self, llm):
        from hipeac_agents.agents.vision_watch.nodes.digest import SignalGroups
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        state = VisionWatchState.model_construct(week="2026-W24")

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        assert "## Also worth watching" not in updates["digest_markdown"]
        assert not [call for call in llm.calls if call[0] is SignalGroups]


class TestGraph:
    def test_build_graph_wires_requested_nodes(self):
        compiled = graph.build_graph(["cluster", "digest"], Services(crawl=None, mail=None, vision=None), FakeLLM())

        assert compiled is not None

    def test_unknown_node_raises(self):
        with pytest.raises(ValueError, match="unknown node"):
            graph.build_graph(["bogus"], Services(crawl=None, mail=None, vision=None), FakeLLM())


class TestMessageAttribution:
    def test_board_mailbox_messages_are_tips(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import attribute_messages
        from hipeac_agents.services.types import MailMessage

        message = MailMessage(inbox_id="in", message_id="m1", from_="colleague@example.com", to=["news@example.com"])

        attributed, tips, unattributed = attribute_messages(message and [message], [], "news@example.com")

        assert tips == [message] and not attributed and not unattributed

    def test_unattributed_senders_go_to_inbox_bucket(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import attribute_messages
        from hipeac_agents.agents.vision_watch.schemas import SourceEntry
        from hipeac_agents.services.types import MailMessage

        source = SourceEntry.model_validate(
            {
                "id": "n1",
                "name": "Newsletter",
                "url": "https://example.com",
                "class": "aggregators",
                "region": "global",
                "tier": 2,
                "independence": "high",
                "stream": "evidence",
                "senders": ["weekly@substack.com"],
            }
        )
        matched = MailMessage(inbox_id="in", message_id="m1", from_="weekly@substack.com", to=["in@agentmail.to"])
        unknown = MailMessage(inbox_id="in", message_id="m2", from_="other@example.com", to=["in@agentmail.to"])

        attributed, tips, unattributed = attribute_messages([matched, unknown], [source], "news@example.com")

        assert [m.message_id for m in attributed["n1"]] == ["m1"]
        assert [m.message_id for m in unattributed] == ["m2"]
        assert not tips

    def test_message_without_a_sender_matches_nothing(self):
        """Regression: matching is bidirectional substring, so an empty sender
        was ``in`` every declared value and got attributed to the first source."""
        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import _sender_matches, attribute_messages
        from hipeac_agents.agents.vision_watch.schemas import SourceEntry
        from hipeac_agents.services.types import MailMessage

        assert _sender_matches("", ["weekly@substack.com"]) is False
        assert _sender_matches("   ", ["weekly@substack.com"]) is False
        assert _sender_matches("weekly@substack.com", ["substack.com"]) is True

        source = SourceEntry.model_validate(
            {
                "id": "n1",
                "name": "Newsletter",
                "url": "https://example.com",
                "class": "aggregators",
                "region": "global",
                "tier": 2,
                "independence": "high",
                "stream": "evidence",
                "senders": ["weekly@substack.com"],
            }
        )
        anonymous = MailMessage(inbox_id="in", message_id="m1", from_="", to=["in@agentmail.to"])

        attributed, _, unattributed = attribute_messages([anonymous], [source], "news@example.com")

        assert attributed["n1"] == []
        assert [m.message_id for m in unattributed] == ["m1"]


class TestUrlDedupe:
    def test_same_url_folds_into_best_tier(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest import node as harvest_node_mod
        from hipeac_agents.agents.vision_watch.schemas import Finding

        def finding(fid: str, tier: int, summary: str) -> Finding:
            return Finding.model_validate(
                {
                    "id": fid,
                    "date": "2026-06-09",
                    "title": "Same story",
                    "url": "https://example.com/story",
                    "source_id": "s",
                    "region": "global",
                    "tier": tier,
                    "theme_ids": ["physical-ai"],
                    "summary": summary,
                }
            )

        findings = [
            finding("a", 3, "aggregator version"),
            finding("b", 2, "first-party version"),
            finding("c", 2, "another newsletter version"),
        ]

        merged = harvest_node_mod._merge_url_duplicates(findings)

        assert len(merged) == 1
        assert merged[0].summary == "first-party version"
        assert merged[0].corroboration == "aggregator version; another newsletter version"

    def test_distinct_urls_survive(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest import node as harvest_node_mod
        from hipeac_agents.agents.vision_watch.schemas import Finding

        def finding(fid: str, url: str) -> Finding:
            return Finding.model_validate(
                {
                    "id": fid,
                    "date": "2026-06-09",
                    "title": "t",
                    "url": url,
                    "source_id": "s",
                    "region": "global",
                    "tier": 2,
                    "theme_ids": ["physical-ai"],
                    "summary": "s",
                }
            )

        findings = [finding("a", "https://example.com/1"), finding("b", "https://example.com/2")]

        merged = harvest_node_mod._merge_url_duplicates(findings)

        assert len(merged) == 2

    def test_winner_keeps_its_own_corroboration(self):
        """Regression: a finding that displaced the primary had its own
        corroboration overwritten with the primary's instead of joined."""
        from hipeac_agents.agents.vision_watch.nodes.harvest import node as harvest_node_mod
        from hipeac_agents.agents.vision_watch.schemas import Finding

        def finding(fid: str, tier: int, summary: str, corroboration: str) -> Finding:
            return Finding.model_validate(
                {
                    "id": fid,
                    "date": "2026-06-09",
                    "title": "Same story",
                    "url": "https://example.com/story",
                    "source_id": "s",
                    "region": "global",
                    "tier": tier,
                    "theme_ids": ["physical-ai"],
                    "summary": summary,
                    "corroboration": corroboration,
                }
            )

        findings = [
            finding("a", 3, "aggregator version", "seen at aggregator"),
            finding("b", 2, "first-party version", "confirmed by vendor"),
        ]

        merged = harvest_node_mod._merge_url_duplicates(findings)

        assert len(merged) == 1
        assert merged[0].summary == "first-party version"
        # Both the winner's own corroboration and the displaced primary's survive.
        assert "confirmed by vendor" in merged[0].corroboration
        assert "seen at aggregator" in merged[0].corroboration
        assert "aggregator version" in merged[0].corroboration


class TestCapSourceVolume:
    """Every source keeps its most significant developments, bounded 2-4."""

    @staticmethod
    def _finding(n: int, source_id: str, tier: int = 2, significance: int = 3) -> object:
        from hipeac_agents.agents.vision_watch.schemas import Finding

        return Finding(
            id="",
            date=date(2026, 6, 12 - n),
            title=f"Item {n}",
            url=f"https://example.com/{source_id}-{n}",
            source_id=source_id,
            region="global",
            tier=tier,
            theme_ids=["physical-ai"],
            datapoint="",
            summary=f"Summary {n}.",
            significance=significance,
        )

    def test_all_significant_qualifying_below_ceiling_kept(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.node import _cap_source_volume

        findings = [self._finding(n, "arxiv-cs-ro", significance=4) for n in range(3)]
        kept, rejected = _cap_source_volume(findings)

        assert len(kept) == 3
        assert rejected == []

    def test_ceiling_trims_significant_overflow(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.node import _SOURCE_KEEP_MAX, _cap_source_volume

        findings = [self._finding(n, "arxiv-cs-ro", significance=5) for n in range(6)]
        kept, rejected = _cap_source_volume(findings)

        assert len(kept) == _SOURCE_KEEP_MAX
        assert len(rejected) == 6 - _SOURCE_KEEP_MAX
        assert {r.reason for r in rejected} == {"source_cap"}
        assert {r.url for r in rejected}.isdisjoint({f.url for f in kept})
        # Newest first within equal significance — deterministic.
        assert {f.url for f in kept} == {f"https://example.com/arxiv-cs-ro-{n}" for n in range(_SOURCE_KEEP_MAX)}

    def test_quiet_source_falls_back_to_minimum(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.node import _SOURCE_KEEP_MIN, _cap_source_volume

        findings = [self._finding(n, "arxiv-cs-ro") for n in range(6)]  # all significance 3
        kept, rejected = _cap_source_volume(findings)

        assert len(kept) == _SOURCE_KEEP_MIN
        assert len(rejected) == 6 - _SOURCE_KEEP_MIN
        # Fallback keeps the newest routine developments.
        assert {f.url for f in kept} == {f"https://example.com/arxiv-cs-ro-{n}" for n in range(_SOURCE_KEEP_MIN)}

    def test_significance_ranks_above_recency(self):
        """Regression: with uniform significance 3, the fallback must keep
        the newest, but a significant older item outranks recent routine
        items."""
        from hipeac_agents.agents.vision_watch.nodes.harvest.node import _cap_source_volume

        findings = [self._finding(n, "arxiv-cs-ro") for n in range(4)]
        findings[3] = self._finding(3, "arxiv-cs-ro", significance=5)  # oldest, most significant
        kept, _ = _cap_source_volume(findings)

        assert "https://example.com/arxiv-cs-ro-3" in {f.url for f in kept}

    def test_small_source_uncapped(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.node import _cap_source_volume

        findings = [self._finding(n, "darpa-news", significance=4) for n in range(4)]
        kept, rejected = _cap_source_volume(findings)

        assert len(kept) == 4
        assert rejected == []


class TestResample:
    async def test_dead_url_is_moved_out_of_findings_not_copied(self):
        """Regression: a finding that failed re-sampling was appended to the
        rejected audit but left in the findings — both files are write-once,
        so the contradiction was permanent."""
        from hipeac_agents.agents.vision_watch.nodes.harvest import node as harvest_node_mod
        from hipeac_agents.agents.vision_watch.schemas import Finding

        def finding(fid: str, url: str) -> Finding:
            return Finding.model_validate(
                {
                    "id": fid,
                    "date": "2026-06-09",
                    "title": f"Story {fid}",
                    "url": url,
                    "source_id": "robot-report",
                    "region": "global",
                    "tier": 2,
                    "theme_ids": ["physical-ai"],
                    "summary": "s",
                }
            )

        # pick_resample takes every 5th finding, so f-01 is the sampled one.
        findings = [finding(f"f-{i:02d}", f"https://example.com/{i}") for i in range(1, 7)]
        crawl = FakeCrawl(pages={f"https://example.com/{i}": ("t", "m") for i in range(2, 7)})
        rejected = []

        kept = await harvest_node_mod._resample(crawl, findings, rejected)

        assert [item.url for item in rejected] == ["https://example.com/1"]
        assert [item.reason for item in rejected] == ["url_404"]
        assert "f-01" not in {f.id for f in kept}
        assert len(kept) == len(findings) - 1

    async def test_live_urls_are_all_kept(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest import node as harvest_node_mod
        from hipeac_agents.agents.vision_watch.schemas import Finding

        findings = [
            Finding.model_validate(
                {
                    "id": f"f-{i:02d}",
                    "date": "2026-06-09",
                    "title": "t",
                    "url": f"https://example.com/{i}",
                    "source_id": "robot-report",
                    "region": "global",
                    "tier": 2,
                    "theme_ids": ["physical-ai"],
                    "summary": "s",
                }
            )
            for i in range(1, 7)
        ]
        crawl = FakeCrawl(pages={f"https://example.com/{i}": ("t", "m") for i in range(1, 7)})
        rejected = []

        kept = await harvest_node_mod._resample(crawl, findings, rejected)

        assert not rejected
        assert len(kept) == len(findings)


class TestResampleProviderError:
    async def test_provider_error_keeps_the_weeks_findings(self):
        """Regression (baseline B12): running out of credits on the fresh
        re-sample fetch aborted the harvest after all the collection work."""
        from hipeac_agents.agents.vision_watch.nodes.harvest import node as harvest_node_mod
        from hipeac_agents.agents.vision_watch.schemas import Finding
        from hipeac_agents.services.crawl import ScrapeQuotaError

        class QuotaCrawl:
            async def scrape(self, url, fresh=False):
                raise ScrapeQuotaError("Insufficient credits")

        findings = [
            Finding.model_validate(
                {
                    "id": f"f-2026-W24-0{i}",
                    "date": "2026-06-09",
                    "title": f"t{i}",
                    "url": f"https://example.com/{i}",
                    "source_id": "s",
                    "region": "global",
                    "tier": 2,
                    "summary": "s",
                }
            )
            for i in range(1, 7)
        ]
        rejected = []

        kept = await harvest_node_mod._resample(QuotaCrawl(), findings, rejected)

        assert len(kept) == len(findings)
        assert not rejected


class TestFeedChannel:
    @pytest.fixture(autouse=True)
    def _setup(self, data_dir, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.DATA_DIR", data_dir)
        monkeypatch.setattr(
            "hipeac_agents.agents.vision_watch.nodes.harvest.channels.http_url_is_dead", lambda url: False
        )

    @pytest.fixture
    def feed_catalog(self, data_dir):
        config = workspace.workspace_root(data_dir) / "config" / "source-catalog.yaml"
        config.write_text(
            "meta:\n"
            "    version: 1\n"
            "sources:\n"
            "    - id: feed-source\n"
            "      name: Feed Source\n"
            "      url: https://example.com/site\n"
            "      feed_url: https://example.com/feed.xml\n"
            "      class: aggregators\n"
            "      themes: [physical-ai]\n"
            "      region: global\n"
            "      tier: 2\n"
            "      independence: high\n"
            "      stream: evidence\n",
            encoding="utf-8",
        )

    @pytest.fixture
    def feed_xml(self):
        return (
            '<?xml version="1.0"?><rss version="2.0"><channel>'
            "<item><title>Humanoid deployed</title><link>https://example.com/item</link>"
            "<pubDate>Fri, 12 Jun 2026 10:00:00 GMT</pubDate>"
            "<description>Robotics milestone.</description></item>"
            "</channel></rss>"
        )

    async def test_feed_parsed_without_firecrawl_or_extraction(self, data_dir, llm, feed_catalog, feed_xml):
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        # sweep skipped: this test isolates the feed channel
        state = VisionWatchState.model_construct(
            week="2026-W24",
            window_start=date(2026, 6, 6),
            window_end=date(2026, 6, 12),
            skip_sweep=True,
        )

        llm.handlers[GateVerdict] = make_gate_handler(["physical-ai"])
        crawl = FakeCrawl(
            pages={"https://example.com/item": ("Humanoid deployed", "Full item text.")},
            feeds={"https://example.com/feed.xml": feed_xml},
        )

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        assert crawl.feed_calls == ["https://example.com/feed.xml"]
        assert not crawl.search_calls
        assert any(f.source_id == "feed-source" and f.access_method == "direct" for f in updates["findings"])
        assert updates["findings"][0].date.isoformat() == "2026-06-12"

    async def test_feed_failure_falls_back_to_page_scrape(self, data_dir, llm, feed_catalog):
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        llm.handlers[CandidateList] = make_candidate_handler(
            [{"title": "Humanoid deployed", "url": "https://example.com/item", "date": "2026-06-09", "summary": "s"}]
        )
        llm.handlers[GateVerdict] = make_gate_handler(["physical-ai"])
        crawl = FakeCrawl(
            pages={
                "https://example.com/site": ("Site", "link https://example.com/item"),
                "https://example.com/item": ("Humanoid deployed", "Full item text."),
            }
        )
        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        assert crawl.feed_calls == ["https://example.com/feed.xml"]
        # Regression (baseline B7): the fallback used to scrape the feed URL again.
        assert "https://example.com/site" in crawl.scrape_calls
        assert "https://example.com/feed.xml" not in crawl.scrape_calls
        assert len(updates["findings"]) == 1
