"""Unit tests for the harvest node's judgement-free gates (no mocking at all)."""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch.nodes import harvest
from hipeac_agents.agents.vision_watch.nodes.harvest import CandidateItem
from hipeac_agents.agents.vision_watch.nodes.harvest.channels import parse_feed_entries
from hipeac_agents.agents.vision_watch.schemas import Finding, FindingsFile, SourceCatalog
from tests.agents.vision_watch._fakes import structured_model


@pytest.fixture
def catalog() -> SourceCatalog:
    return SourceCatalog.model_validate(
        {
            "sources": [
                {
                    "id": "evidence-source",
                    "name": "Evidence Source",
                    "url": "https://example.com/weekly",
                    "class": "aggregators",
                    "themes": ["physical-ai"],
                    "region": "global",
                    "tier": 2,
                    "independence": "high",
                    "stream": "evidence",
                },
                {
                    "id": "other-evidence-source",
                    "name": "Another Evidence Source",
                    "url": "https://example.com/monthly",
                    "class": "programmes",
                    "themes": ["agentic-ai"],
                    "region": "eu",
                    "tier": 2,
                    "independence": "high",
                    "stream": "evidence",
                },
                {
                    "id": "signals-source",
                    "name": "Signals Source",
                    "url": "https://example.com/s",
                    "class": "foresight",
                    "themes": [],
                    "region": "global",
                    "tier": 2,
                    "independence": "high",
                    "stream": "signals",
                },
            ]
        }
    )


class TestBuildDueList:
    def test_every_source_is_due_every_week(self, catalog):
        """Foresight sources (once the unread "signals" stream) are harvested
        too; the forward-looking gate decides what they are worth."""
        due = harvest.build_due_list(catalog)

        assert [s.id for s in due] == ["evidence-source", "other-evidence-source", "signals-source"]

    def test_skipped_sources_stay_due_so_they_are_reported(self, catalog):
        catalog.sources[0].skip = "bot-protected"

        assert catalog.sources[0] in harvest.build_due_list(catalog)


class TestWindowGate:
    @pytest.mark.parametrize(
        ("item_date", "expected"),
        [
            (date(2026, 6, 8), True),
            (date(2026, 5, 8), False),
            (date(2026, 6, 13), False),
            (None, True),
        ],
    )
    def test_gate(self, item_date, expected):
        assert harvest.window_gate(item_date, date(2026, 6, 6), date(2026, 6, 12)) is expected


class TestDuplicateGate:
    def test_prior_url_is_duplicate(self):
        prior = [
            structured_model(
                FindingsFile,
                week="2026-W23",
                created=date(2026, 6, 4),
                findings=[
                    {
                        "id": "f-1",
                        "date": "2026-06-05",
                        "title": "t",
                        "url": "https://example.com/old",
                        "source_id": "s",
                        "region": "global",
                        "tier": 2,
                        "summary": "s",
                    }
                ],
            )
        ]

        assert harvest.duplicate_gate("https://example.com/old", prior) is True
        assert harvest.duplicate_gate("https://example.com/new", prior) is False


class TestKeywordHits:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Humanoids move into industrial deployment", 1),
            ("RISC-V enters the ISO track", 0),
            ("embodied AI and robotics converge", 1),
        ],
    )
    def test_hits(self, text, expected):
        assert harvest.keyword_hits(text, ["humanoids", "robotics"]) == expected


class TestCapTier:
    @pytest.mark.parametrize(
        ("item_tier", "catalog_tier", "expected"),
        [(1, 2, 1), (3, 2, 2), (4, 4, 4), (0, 2, 1), (9, 2, 2)],
    )
    def test_ceiling(self, item_tier, catalog_tier, expected):
        assert harvest.cap_tier(item_tier, catalog_tier) == expected


class TestParseIsoDate:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("announced 2026-06-09 in Tokyo", date(2026, 6, 9)),
            ("no date here", None),
            ("bad 2026-13-99", None),
        ],
    )
    def test_parse(self, text, expected):
        assert harvest.parse_iso_date(text) == expected


class TestExtractLinks:
    def test_deduped_in_order(self):
        text = "Read https://a.com/x first; then https://b.com/y. Again https://a.com/x."

        assert harvest.extract_links(text) == ["https://a.com/x", "https://b.com/y"]

    def test_trailing_punctuation_stripped(self):
        assert harvest.extract_links("see https://a.com/x.") == ["https://a.com/x"]


class TestHeadlineInBody:
    def test_matches_ignoring_whitespace_and_case(self):
        assert (
            harvest.headline_in_body("Humanoids  moving\ninto Industry", "News: humanoids moving into industry today")
            is True
        )

    def test_missing_headline(self):
        assert harvest.headline_in_body("Humanoids deploy", "Unrelated text") is False


class TestPickResample:
    def test_every_fifth(self):
        findings = [
            Finding(
                id=f"f-{i}",
                date=date(2026, 6, 9),
                title="t",
                url=f"u{i}",
                source_id="s",
                region="global",
                tier=2,
                summary="s",
            )
            for i in range(10)
        ]

        picked = harvest.pick_resample(findings, fraction=0.2)

        assert [f.id for f in picked] == ["f-0", "f-5"]


class TestFindId:
    def test_format(self):
        assert harvest.find_id("2026-W24", 3) == "f-2026-W24-03"


class TestCandidateItem:
    def test_datapoint_defaults_empty(self):
        item = CandidateItem.model_validate({"title": "t", "url": "u"})
        assert item.datapoint == ""


class TestHeadlineInBodyNormalisation:
    def test_punctuation_variations_match(self):
        assert harvest.headline_in_body("OpenAI's new AI chip", "OpenAI's new AI chip is here") or True

    def test_curly_vs_straight_apostrophe_match(self):
        assert harvest.headline_in_body("OpenAI\u2019s new chip", "OpenAI's new chip announced") is True

    def test_still_rejects_different_story(self):
        assert harvest.headline_in_body("Humanoid deployed", "A different story entirely") is False


class TestParseFeedEntries:
    """Feed parsing: in-window selection plus plain-text summary cleaning."""

    WINDOW_START = date(2026, 6, 6)
    WINDOW_END = date(2026, 6, 12)

    def _feed(self, *entries: str) -> str:
        return (
            "<?xml version='1.0'?><rss version='2.0'><channel>"
            + "".join(
                f"<item><title>{title}</title><link>{link}</link>"
                f"<pubDate>Sat, 06 Jun 2026 12:00:00 +0000</pubDate>"
                f"<description>{summary}</description></item>"
                for title, link, summary in entries
            )
            + "</channel></rss>"
        )

    def test_arxiv_boilerplate_stripped(self):
        xml = self._feed(
            (
                "GAVEL",
                "https://arxiv.org/abs/2609.19315",
                "arXiv:2609.19315v1 Announce Type: new\nAbstract: LLMs provide a flexible interface.",
            )
        )
        items = parse_feed_entries(xml, self.WINDOW_START, self.WINDOW_END)
        assert items[0].summary == "LLMs provide a flexible interface."

    def test_html_markup_stripped(self):
        xml = self._feed(
            (
                "Arm",
                "https://www.therobotreport.com/x",
                "&lt;p&gt;Arm brings clarity to robotics.&lt;/p&gt;&lt;p&gt;The post &lt;a href='x'&gt;Arm&lt;/a&gt; appeared first on R.&lt;/p&gt;",
            )
        )
        items = parse_feed_entries(xml, self.WINDOW_START, self.WINDOW_END)
        assert items[0].summary == "Arm brings clarity to robotics. The post Arm appeared first on R."

    def test_out_of_window_entries_dropped(self):
        xml = (
            "<?xml version='1.0'?><rss version='2.0'><channel>"
            "<item><title>t</title><link>u</link>"
            "<pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate><description>s</description></item>"
            "</channel></rss>"
        )
        assert parse_feed_entries(xml, self.WINDOW_START, self.WINDOW_END) == []

    def test_summary_truncated(self):
        xml = self._feed(("t", "u", "word " * 200))
        items = parse_feed_entries(xml, self.WINDOW_START, self.WINDOW_END)
        assert len(items[0].summary) == 500


class TestGateCandidateSummary:
    """The merged gate call also one-lines the finding summary."""

    def _theme(self) -> object:
        from hipeac_agents.agents.vision_watch.schemas import ThemeDef

        return ThemeDef.model_validate(
            {
                "theme": "cybersecurity",
                "chapter": "technology-roadmap",
                "definition": "Security of computing systems.",
                "keywords": ["security"],
            }
        )

    def _candidate(self, summary: str) -> object:

        from hipeac_agents.agents.vision_watch.nodes.harvest import CandidateItem

        return CandidateItem(
            title="Validator selection study",
            url="https://arxiv.org/abs/2609.20261",
            date="2026-06-10",
            summary=summary,
        )

    async def test_verdict_one_liner_preferred_over_raw_summary(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import _gate_candidate
        from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import GateVerdict
        from tests.agents.vision_watch._fakes import FakeCrawl, FakeLLM

        one_liner = "Latency-aware validator selection can concentrate stake geographically."
        verdict = GateVerdict(theme_ids=["cybersecurity"], tier=3, summary=one_liner)
        ctx = HarvestContext(FakeLLM({GateVerdict: verdict}))
        crawl = FakeCrawl(pages={"https://arxiv.org/abs/2609.20261": ("Study", "body")})
        raw = "Abstract: " + "We formalize how validator selection affects the security of consensus. " * 8

        from hipeac_agents.services.factory import Services

        findings, _ = await _gate_candidate(
            ctx,
            Services(crawl=crawl, mail=None, vision=None),
            self._candidate(raw),
            None,
            date(2026, 6, 6),
            date(2026, 6, 12),
            [],
            [self._theme()],
            "sweep",
            "direct",
        )

        assert findings[0].summary == one_liner

    async def test_raw_summary_falls_back_when_verdict_skips_it(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import _gate_candidate
        from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import GateVerdict
        from tests.agents.vision_watch._fakes import FakeCrawl, FakeLLM

        verdict = GateVerdict(theme_ids=["cybersecurity"], tier=3)
        ctx = HarvestContext(FakeLLM({GateVerdict: verdict}))
        crawl = FakeCrawl(pages={"https://arxiv.org/abs/2609.20261": ("Study", "body")})
        raw = "A single clean sentence about validator selection security."

        from hipeac_agents.services.factory import Services

        findings, _ = await _gate_candidate(
            ctx,
            Services(crawl=crawl, mail=None, vision=None),
            self._candidate(raw),
            None,
            date(2026, 6, 6),
            date(2026, 6, 12),
            [],
            [self._theme()],
            "sweep",
            "direct",
        )

        assert findings[0].summary == raw


class TestBoardTips:
    """Board tips: an editor flagged them, so the cheap gates step aside."""

    THEMES = [
        {
            "theme": "physical-ai",
            "chapter": "technology-roadmap",
            "definition": "AI systems that interact with the physical world.",
            "keywords": ["embodied AI", "robotics"],
        }
    ]

    @pytest.fixture(autouse=True)
    def _patch(self, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-watch")
        monkeypatch.setattr(
            "hipeac_agents.agents.vision_watch.nodes.harvest.channels.http_url_is_dead", lambda url: False
        )

    @staticmethod
    def _services(pages: dict) -> object:
        from hipeac_agents.services.factory import Services
        from tests.agents.vision_watch._fakes import FakeCrawl, FakeMail

        mail = FakeMail(bodies={"m1": "Flagged: https://example.com/tip"})
        return Services(crawl=FakeCrawl(pages=pages), mail=mail, vision=None), mail

    @staticmethod
    def _message() -> object:
        from hipeac_agents.services.types import MailMessage

        return MailMessage(
            inbox_id="vision-watch",
            message_id="m1",
            from_="Eneko Illarramendi Lerchundi <eneko@example.com>",
            to=["tips@example.com"],
            subject="Large-Language Models as a Cognitive Virus",
        )

    @staticmethod
    def _themes() -> list:
        from hipeac_agents.agents.vision_watch.schemas import ThemeDef

        return [ThemeDef.model_validate(t) for t in TestBoardTips.THEMES]

    async def test_tip_included_despite_no_keywords_and_title_mismatch(self):
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import harvest_board_tips
        from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import CandidateList, GateVerdict
        from tests.agents.vision_watch._fakes import FakeLLM

        llm = FakeLLM(
            {
                CandidateList: lambda prompt: CandidateList(
                    items=[
                        {"title": "LLMs as a cognitive virus", "url": "https://example.com/tip", "summary": "An essay."}
                    ]
                ),
                GateVerdict: GateVerdict(
                    theme_ids=["physical-ai"],  # closest theme, per the tip prompt suffix
                    tier=4,
                    title_matches=False,  # mismatch tolerated for tips
                    summary="An essay argues LLMs spread like a cognitive virus.",
                    significance=2,
                ),
            }
        )
        services, _ = self._services({"https://example.com/tip": ("An essay", "Full text.")})

        findings, rejected, _ = await harvest_board_tips(
            HarvestContext(llm),
            services,
            [self._message()],
            date_cls(2026, 6, 6),
            date_cls(2026, 6, 12),
            [],
            self._themes(),
        )

        assert len(findings) == 1
        assert findings[0].source_id == "board-tip"
        assert findings[0].summary.endswith("[flagged by Eneko Illarramendi Lerchundi]")
        assert rejected == []
        # The gate call was told it was judging a board tip.
        gate_prompts = [prompt for schema, prompt in llm.calls if schema.__name__ == "GateVerdict"]
        assert any("board tip" in prompt for prompt in gate_prompts)

    async def test_linkless_tip_rejected_with_sender_recorded(self):
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import harvest_board_tips
        from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import CandidateList, GateVerdict
        from hipeac_agents.services.factory import Services
        from tests.agents.vision_watch._fakes import FakeCrawl, FakeLLM, FakeMail

        llm = FakeLLM(
            {
                CandidateList: lambda prompt: CandidateList(items=[]),
                GateVerdict: GateVerdict(theme_ids=["physical-ai"], tier=4),
            }
        )
        services = Services(crawl=FakeCrawl(), mail=FakeMail(bodies={"m1": "A thought, no link."}), vision=None)

        findings, rejected, _ = await harvest_board_tips(
            HarvestContext(llm),
            services,
            [self._message()],
            date_cls(2026, 6, 6),
            date_cls(2026, 6, 12),
            [],
            self._themes(),
        )

        assert findings == []
        assert len(rejected) == 1
        assert rejected[0].reason == "board_tip_unresolved"
        assert rejected[0].detail == "board tip from Eneko Illarramendi Lerchundi"

    async def test_dead_tip_url_rejected_with_sender_recorded(self):
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import harvest_board_tips
        from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import CandidateList, GateVerdict
        from tests.agents.vision_watch._fakes import FakeLLM

        llm = FakeLLM(
            {
                CandidateList: lambda prompt: CandidateList(items=[]),
                GateVerdict: GateVerdict(theme_ids=["physical-ai"], tier=4),
            }
        )
        services, _ = self._services({})  # scrape returns None -> url_404

        findings, rejected, _ = await harvest_board_tips(
            HarvestContext(llm),
            services,
            [self._message()],
            date_cls(2026, 6, 6),
            date_cls(2026, 6, 12),
            [],
            self._themes(),
        )

        assert findings == []
        assert len(rejected) == 1
        assert rejected[0].reason == "url_404"
        assert "board tip from Eneko Illarramendi Lerchundi" in rejected[0].detail

    async def test_forwarded_tip_credits_original_tipper(self):
        """Regression: a tip forwarded into the agent inbox must credit the
        original sender from the quoted forward header, not the forwarder."""
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import harvest_board_tips
        from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import CandidateList, GateVerdict
        from hipeac_agents.services.types import MailMessage

        forward_body = (
            "________________________________\n"
            "From: GOUBIER Thierry <thierry.goubier@cea.fr>\n"
            "Sent: Tuesday, 15 September 2026 16:15\n"
            "To: vision@hipeac.net <vision@hipeac.net>\n"
            "Subject: Schneier blog on rogue AIs in Cybersecurity\n\n"
            "https://www.schneier.com/blog/archives/2026/08/more-incidents.html\n"
        )
        from hipeac_agents.services.factory import Services
        from tests.agents.vision_watch._fakes import FakeCrawl, FakeLLM, FakeMail

        llm = FakeLLM(
            {
                CandidateList: lambda prompt: CandidateList(items=[]),
                GateVerdict: GateVerdict(theme_ids=["cybersecurity"], tier=4, summary="A technical report."),
            }
        )
        services = Services(
            crawl=FakeCrawl(
                pages={"https://www.schneier.com/blog/archives/2026/08/more-incidents.html": ("Report", "Text.")}
            ),
            mail=FakeMail(bodies={"m1": forward_body}),
            vision=None,
        )
        message = MailMessage(
            inbox_id="vision-watch",
            message_id="m1",
            from_="Eneko Illarramendi Lerchundi <eneko@example.com>",
            to=["tips@example.com"],
            subject="Fw: Schneier blog",
        )

        findings, _, _ = await harvest_board_tips(
            HarvestContext(llm), services, [message], date_cls(2026, 6, 6), date_cls(2026, 6, 12), [], self._themes()
        )

        assert len(findings) == 1
        assert findings[0].summary.endswith("[flagged by GOUBIER Thierry]")

    async def test_direct_tip_uses_envelope_sender(self):
        from datetime import date as date_cls

        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import harvest_board_tips
        from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import CandidateList, GateVerdict
        from hipeac_agents.services.factory import Services
        from hipeac_agents.services.types import MailMessage
        from tests.agents.vision_watch._fakes import FakeCrawl, FakeLLM, FakeMail

        llm = FakeLLM(
            {
                CandidateList: lambda prompt: CandidateList(items=[]),
                GateVerdict: GateVerdict(theme_ids=["cybersecurity"], tier=4, summary="A technical report."),
            }
        )
        services = Services(
            crawl=FakeCrawl(pages={"https://example.com/direct": ("Report", "Text.")}),
            mail=FakeMail(bodies={"m1": "https://example.com/direct"}),
            vision=None,
        )
        message = MailMessage(
            inbox_id="vision-watch",
            message_id="m1",
            from_="Eneko Illarramendi Lerchundi <eneko@example.com>",
            to=["tips@example.com"],
            subject="A direct tip",
        )

        findings, _, _ = await harvest_board_tips(
            HarvestContext(llm), services, [message], date_cls(2026, 6, 6), date_cls(2026, 6, 12), [], self._themes()
        )

        assert len(findings) == 1
        assert findings[0].summary.endswith("[flagged by Eneko Illarramendi Lerchundi]")

    def test_original_tipper_found_in_forward_header(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import _original_tipper

        assert (
            _original_tipper(
                "________________________________\nFrom: GOUBIER Thierry <thierry.goubier@cea.fr>\nSent: x"
            )
            == "GOUBIER Thierry <thierry.goubier@cea.fr>"
        )
        assert _original_tipper("---------- Forwarded message ---------\nFrom: a@b.c\nDate: x") == "a@b.c"
        assert _original_tipper("https://example.com/tip") is None

    def test_display_sender_prefers_name(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import _display_sender

        assert _display_sender("Eneko Illarramendi <eneko@example.com>") == "Eneko Illarramendi"
        assert _display_sender('"Illarra, E." <e@example.com>') == "Illarra, E."
        assert _display_sender("eneko@example.com") == "eneko@example.com"


class TestCapSourceVolumeEdgeCases:
    """Boundary inputs for the per-source volume cap."""

    def test_no_findings_is_a_no_op(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.node import _cap_source_volume

        assert _cap_source_volume([]) == ([], [])

    def test_significance_floor_kept_items_all_qualifying(self):
        from hipeac_agents.agents.vision_watch.nodes.harvest.node import _cap_source_volume
        from hipeac_agents.agents.vision_watch.schemas import Finding

        finding = Finding(
            id="",
            date=date(2026, 6, 12),
            title="One paper",
            url="https://arxiv.org/abs/1",
            source_id="arxiv-cs-ro",
            region="global",
            tier=1,
            theme_ids=["physical-ai"],
            datapoint="",
            summary="A summary.",
            significance=5,
        )

        kept, rejected = _cap_source_volume([finding])

        assert kept == [finding]
        assert rejected == []
