"""Collection channel tests: arXiv, feed fallbacks and flags, feed snapshots."""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.harvest import channels
from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
from hipeac_agents.agents.vision_watch.nodes.harvest.models import CandidateItem, CandidateList, GateVerdict
from hipeac_agents.agents.vision_watch.schemas import SourceEntry
from hipeac_agents.agents.vision_watch.snapshots import snapshot_feeds
from hipeac_agents.services.factory import Services
from tests.agents.vision_watch._fakes import FakeCrawl, FakeLLM, make_candidate_handler, make_gate_handler


WINDOW = (date(2026, 9, 19), date(2026, 9, 25))

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>1</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2609.01234v1</id>
    <published>2026-09-22T17:04:24Z</published>
    <title>A Chiplet
      Interconnect for Agents</title>
    <summary>We present an open chiplet interconnect for agentic workloads.</summary>
    <link href="http://arxiv.org/abs/2609.01234v1" rel="alternate" type="text/html"/>
  </entry>
</feed>"""


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
        "class": "aggregators",
        "region": "global",
        "tier": 2,
        "independence": "high",
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
    def test_query_bounds_the_submission_dates(self):
        url = channels.arxiv_query_url("cs.AR", *WINDOW)

        assert "cat%3Acs.AR" in url
        assert "submittedDate%3A%5B202609190000+TO+202609252359%5D" in url

    def test_parses_title_link_date_and_total(self):
        items, total = channels.parse_arxiv_entries(ARXIV_XML)

        assert total == 1
        assert items[0].title == "A Chiplet Interconnect for Agents"
        assert items[0].url == "http://arxiv.org/abs/2609.01234v1"
        assert items[0].date == "2026-09-22"

    async def test_harvests_the_week_without_scraping(self, themes):
        """Regression (baseline B6): arXiv RSS is empty at weekends, so the
        preprint sources had produced nothing; the API answers for any week."""
        source = _source(id="arxiv-cs-ar", arxiv="cs.AR", url="https://arxiv.org/list/cs.AR/new")
        crawl = FakeCrawl(feeds={channels.arxiv_query_url("cs.AR", *WINDOW): ARXIV_XML})
        llm = FakeLLM({GateVerdict: make_gate_handler(["agentic-ai"])})

        findings, rejected, outcome = await channels.harvest_arxiv_source(
            HarvestContext(llm), Services(crawl=crawl, mail=None, vision=None), source, *WINDOW, [], themes
        )

        assert [f.title for f in findings] == ["A Chiplet Interconnect for Agents"]
        assert findings[0].date == date(2026, 9, 22)
        assert not crawl.scrape_calls, "the API already carries the paper; no scrape needed"
        assert outcome.status == "collected"

    async def test_unreachable_api_is_flagged(self, themes):
        source = _source(id="arxiv-cs-ar", arxiv="cs.AR")

        _, _, outcome = await channels.harvest_arxiv_source(
            HarvestContext(FakeLLM()), Services(crawl=FakeCrawl(), mail=None, vision=None), source, *WINDOW, [], themes
        )

        assert outcome.status == "failed"
        assert outcome.flags == ["feed_fetch_failed"]


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
        earlier = CandidateItem(title="Robotics arm shipped", url="https://example.com/early", date="2026-09-19")
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
                ("A", "https://example.com/a", "Sat, 19 Sep 2026 10:00:00 GMT")
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
