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
            "      stream: evidence\n"
            "      web: false\n"
            "      newsletter: true\n",
            encoding="utf-8",
        )

        message = MailMessage(
            inbox_id="vision-news", message_id="m1", from_="newsletter@substack.com", subject="Weekly"
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

        assert any(f.access_method == "newsletter" for f in updates["findings"])

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

        state = VisionWatchState.model_construct(week="2026-W24")

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
            VisionWatchState.model_construct(week="2026-W24"),
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

    async def test_skip_send_flag_blocks_email(self, llm, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.HIPEAC_VISION_BOARD_EMAIL", "news@example.com")
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")
        from hipeac_agents.agents.vision_watch.state import VisionWatchState

        llm.handlers[DigestProse] = lambda prompt: DigestProse.model_validate(
            {"lead": "L", "why_it_matters": "W", "europe": "GAP", "maturity": "watch, low"}
        )
        mail = FakeMail()
        state = VisionWatchState.model_construct(week="2026-W24", skip_send=True)

        updates = await digest_node_mod.digest_node(
            state, services=Services(crawl=None, mail=mail, vision=None), llm=llm
        )

        assert updates["digest_sent"] is False
        assert not mail.sent
        assert (workspace.weekly_digest_dir() / "digest-2026-W24.md").exists()

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

        one_big_thing = updates["digest_markdown"].split("## One big thing")[1].split("## Across the themes")[0]
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

        one_big_thing = updates["digest_markdown"].split("## One big thing")[1].split("## Across the themes")[0]
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

        across = updates["digest_markdown"].split("## Across the themes")[1].split("## Trending this week")[0]
        shared_lines = [line for line in across.splitlines() if "https://example.com/shared" in line]
        assert len(shared_lines) == 1
        assert "in cluster-a, cluster-b" in shared_lines[0]

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
                "https://example.com/feed.xml": ("Feed", "link https://example.com/item"),
                "https://example.com/item": ("Humanoid deployed", "Full item text."),
            }
        )
        state = VisionWatchState(week="2026-W24", window_start=date(2026, 6, 6), window_end=date(2026, 6, 12))

        updates = await harvest_node_mod.harvest_node(state, services=_services(crawl), llm=llm)

        assert crawl.feed_calls == ["https://example.com/feed.xml"]
        assert "https://example.com/feed.xml" in crawl.scrape_calls
        assert len(updates["findings"]) == 1
