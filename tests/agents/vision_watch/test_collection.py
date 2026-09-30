"""Collection channel tests: arXiv, feed fallbacks and flags, feed snapshots."""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.harvest import channels
from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
from hipeac_agents.agents.vision_watch.nodes.harvest.models import (
    CandidateItem,
    CandidateList,
    GateVerdict,
    NotableSelection,
)
from hipeac_agents.agents.vision_watch.schemas import SourceEntry
from hipeac_agents.agents.vision_watch.snapshots import snapshot_feeds
from hipeac_agents.services.factory import Services
from tests.agents.vision_watch._fakes import FakeCrawl, FakeLLM, make_candidate_handler, make_gate_handler


WINDOW = (date(2026, 9, 21), date(2026, 9, 27))  # 2026-W39, Monday–Sunday


def _listing_entry(n: int, paper_id: str, title: str) -> str:
    return (
        f'<dt><a name=\'item{n}\'>[{n}]</a><a href ="/abs/{paper_id}" title="Abstract" id="{paper_id}">'
        f"arXiv:{paper_id}</a></dt><dd><div class='meta'><div class='list-title mathjax'>"
        f"<span class='descriptor'>Title:</span>\n          {title}\n        </div></div></dd>"
    )


ARXIV_LISTING = (
    "<html><body>"
    "<h3>Mon, 28 Sep 2026 (showing 1 of 1 entries )</h3>"
    + _listing_entry(1, "2609.40000", "Next Week Paper")
    + "<h3>Tue, 22 Sep 2026 (showing 2 of 2 entries )</h3>"
    + _listing_entry(2, "2609.01234", "A Chiplet\n Interconnect for &amp; Agents")
    + _listing_entry(3, "2609.01235", "Yet Another Benchmark")
    + "<h3>Fri, 18 Sep 2026 (showing 1 of 1 entries )</h3>"
    + _listing_entry(4, "2609.00001", "Last Week Paper")
    + "</body></html>"
)

ARXIV_ABSTRACT_PAGE = (
    '<blockquote class="abstract mathjax">\n<span class="descriptor">Abstract:</span>'
    "We present an open <b>chiplet</b> interconnect for agentic workloads.\n</blockquote>"
)


def _rss(*items: tuple[str, str, str]) -> str:
    body = "".join(
        f"<item><title>{title}</title><link>{link}</link><pubDate>{pub}</pubDate>"
        "<description>Robotics milestone.</description></item>"
        for title, link, pub in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{body}</channel></rss>'


def _source(**overrides) -> SourceEntry:
    data = {
        "id": "src",
        "name": "Src",
        "url": "https://example.com/site",
        "class": "press",
        "region": "global",
        "tier": 2,
        "stream": "evidence",
    }
    return SourceEntry.model_validate({**data, **overrides})


@pytest.fixture(autouse=True)
def _alive(monkeypatch):
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.nodes.harvest.channels.http_url_is_dead", lambda url: False)


@pytest.fixture
def themes(data_dir):
    return workspace.read_themes(data_dir)


class TestArxiv:
    def test_listing_keeps_papers_announced_in_the_window(self):
        items = channels.parse_arxiv_listing(ARXIV_LISTING, *WINDOW)

        assert [(i.title, i.url, i.date) for i in items] == [
            ("A Chiplet Interconnect for & Agents", "https://arxiv.org/abs/2609.01234", "2026-09-22"),
            ("Yet Another Benchmark", "https://arxiv.org/abs/2609.01235", "2026-09-22"),
        ]

    def test_abstract_is_plain_text(self):
        assert channels.parse_arxiv_abstract(ARXIV_ABSTRACT_PAGE) == (
            "We present an open chiplet interconnect for agentic workloads."
        )

    async def test_picks_notable_titles_then_fetches_only_their_abstracts(self, themes, monkeypatch):
        """Regression (baseline B6): arXiv RSS is empty at weekends and the API
        host rejects Python clients; the past-week listing serves any weekday."""
        monkeypatch.setattr("asyncio.sleep", _no_sleep)
        source = _source(id="arxiv-cs-ar", arxiv="cs.AR", url="https://arxiv.org/list/cs.AR/new")
        crawl = FakeCrawl(
            feeds={
                channels.ARXIV_LISTING.format(category="cs.AR"): ARXIV_LISTING,
                "https://arxiv.org/abs/2609.01234": ARXIV_ABSTRACT_PAGE,
            }
        )
        llm = FakeLLM(
            {
                NotableSelection: NotableSelection(indices=[0, 7]),
                GateVerdict: make_gate_handler(["agentic-ai"]),
            }
        )

        findings, rejected, outcome = await channels.harvest_arxiv_source(
            HarvestContext(llm), Services(crawl=crawl, mail=None, vision=None), source, *WINDOW, [], themes
        )

        assert [f.title for f in findings] == ["A Chiplet Interconnect for & Agents"]
        assert findings[0].date == date(2026, 9, 22)
        assert [(r.claimed_title, r.reason) for r in rejected] == [("Yet Another Benchmark", "off_theme")]
        assert "https://arxiv.org/abs/2609.01235" not in crawl.feed_calls, "dropped papers cost no fetch"
        assert not crawl.scrape_calls, "nothing goes through the crawl provider"
        gate_prompt = next(prompt for schema, prompt in llm.calls if schema is GateVerdict)
        assert "open chiplet interconnect" in gate_prompt, "the verdict sees the abstract"
        assert outcome.status == "collected"

    async def test_unreachable_listing_is_flagged(self, themes, monkeypatch):
        monkeypatch.setattr(channels, "ARXIV_PAUSE_SECONDS", 0)
        source = _source(id="arxiv-cs-ar", arxiv="cs.AR")

        _, _, outcome = await channels.harvest_arxiv_source(
            HarvestContext(FakeLLM()), Services(crawl=FakeCrawl(), mail=None, vision=None), source, *WINDOW, [], themes
        )

        assert outcome.status == "failed"
        assert outcome.flags == ["feed_fetch_failed"]

    async def test_categories_never_hit_arxiv_at_once(self, themes, monkeypatch):
        """Regression: the categories' listings went out together and arXiv refused 7 of 8 (W39 harvest)."""
        import asyncio

        monkeypatch.setattr(channels, "ARXIV_PAUSE_SECONDS", 0)
        in_flight, peak = 0, 0

        class CountingCrawl(FakeCrawl):
            async def fetch_feed(self, url):
                nonlocal in_flight, peak
                in_flight += 1
                peak = max(peak, in_flight)
                await asyncio.sleep(0.01)
                in_flight -= 1

        ctx = HarvestContext(FakeLLM())
        services = Services(crawl=CountingCrawl(), mail=None, vision=None)
        await asyncio.gather(
            *(
                channels.harvest_arxiv_source(ctx, services, _source(id=f"arxiv-{c}", arxiv=c), *WINDOW, [], themes)
                for c in ("cs.AR", "cs.DC", "cs.RO")
            )
        )

        assert peak == 1


async def _no_sleep(_seconds):
    return None


class TestFeedFallbacks:
    @pytest.fixture
    def llm(self):
        return FakeLLM(
            {
                CandidateList: make_candidate_handler(
                    [{"title": "Humanoid deployed", "url": "https://example.com/item", "date": "2026-09-22"}]
                ),
                GateVerdict: make_gate_handler(["physical-ai"]),
            }
        )

    async def test_empty_feed_falls_back_to_the_page_and_is_flagged(self, themes, llm):
        source = _source(feed_url="https://example.com/feed.xml")
        crawl = FakeCrawl(
            feeds={"https://example.com/feed.xml": _rss()},
            pages={
                "https://example.com/site": ("Site", "Humanoid deployed https://example.com/item"),
                "https://example.com/item": ("Humanoid deployed", "text"),
            },
        )

        findings, _, outcome = await channels.harvest_feed_source(
            HarvestContext(llm), Services(crawl=crawl, mail=None, vision=None), source, *WINDOW, [], themes
        )

        assert "https://example.com/site" in crawl.scrape_calls
        assert len(findings) == 1
        assert outcome.flags == ["feed_empty"]

    async def test_failed_feed_is_flagged(self, themes, llm):
        source = _source(feed_url="https://example.com/feed.xml")
        crawl = FakeCrawl(pages={"https://example.com/site": ("Site", "x"), "https://example.com/item": ("H", "t")})

        _, _, outcome = await channels.harvest_feed_source(
            HarvestContext(llm), Services(crawl=crawl, mail=None, vision=None), source, *WINDOW, [], themes
        )

        assert outcome.flags == ["feed_fetch_failed"]

    async def test_feed_not_reaching_saturday_is_flagged_truncated(self, themes, llm):
        source = _source(feed_url="https://example.com/feed.xml")
        xml = _rss(("Humanoid deployed", "https://example.com/item", "Wed, 23 Sep 2026 10:00:00 GMT"))
        crawl = FakeCrawl(feeds={"https://example.com/feed.xml": xml}, pages={"https://example.com/item": ("H", "t")})

        _, _, outcome = await channels.harvest_feed_source(
            HarvestContext(llm), Services(crawl=crawl, mail=None, vision=None), source, *WINDOW, [], themes
        )

        assert outcome.flags == ["feed_truncated"]

    async def test_snapshot_entries_are_merged_and_clear_truncation(self, themes, llm):
        """Regression (baseline B24): busy feeds lost the start of the week."""
        source = _source(feed_url="https://example.com/feed.xml")
        xml = _rss(("Humanoid deployed", "https://example.com/item", "Wed, 23 Sep 2026 10:00:00 GMT"))
        earlier = CandidateItem(title="Robotics arm shipped", url="https://example.com/early", date="2026-09-21")
        crawl = FakeCrawl(
            feeds={"https://example.com/feed.xml": xml},
            pages={"https://example.com/item": ("H", "t"), "https://example.com/early": ("Robotics arm shipped", "t")},
        )

        findings, _, outcome = await channels.harvest_feed_source(
            HarvestContext(llm),
            Services(crawl=crawl, mail=None, vision=None),
            source,
            *WINDOW,
            [],
            themes,
            snapshot=[earlier],
        )

        assert {f.url for f in findings} == {"https://example.com/item", "https://example.com/early"}
        assert outcome.flags == []

    def test_every_in_window_entry_is_considered(self):
        items = [(f"Robot {i}", f"https://example.com/{i}", "Tue, 22 Sep 2026 10:00:00 GMT") for i in range(60)]

        assert len(channels.parse_feed_entries(_rss(*items), *WINDOW)) == 60


class TestSnapshotFeeds:
    async def test_captures_and_merges_the_open_week(self, data_dir, monkeypatch):
        monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.DATA_DIR", data_dir)
        feeds = {
            "https://example.com/robot-report/feed": _rss(
                ("A", "https://example.com/a", "Mon, 21 Sep 2026 10:00:00 GMT")
            )
        }

        async def fetch(url):
            return feeds.get(url)

        await snapshot_feeds(fetch, date(2026, 9, 21))
        feeds["https://example.com/robot-report/feed"] = _rss(
            ("B", "https://example.com/b", "Tue, 22 Sep 2026 10:00:00 GMT")
        )
        held = await snapshot_feeds(fetch, date(2026, 9, 23))

        assert held == {"robot-report": 2}
        assert [i.url for i in workspace.read_feed_snapshot("2026-W39", "robot-report")] == [
            "https://example.com/a",
            "https://example.com/b",
        ]
