"""Unit tests for the crawl scrape cache (inner client faked)."""

import pytest

from hipeac_agents.services.crawl import CachedCrawl
from hipeac_agents.services.types import ScrapeResult


class CountingCrawl:
    """Fake inner client: counts scrapes so cache hits are observable."""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.scrape_calls: list[tuple[str, bool]] = []

    async def scrape(self, url: str, fresh: bool = False):
        self.scrape_calls.append((url, fresh))
        if url not in self.pages:
            return None
        return ScrapeResult(url=url, title="t", markdown=self.pages[url])

    async def search(self, query: str, limit: int = 5):
        return []


@pytest.fixture
def cache_root(tmp_path):
    return tmp_path / "scrapes"


async def test_second_scrape_hits_cache(tmp_path):
    inner = CountingCrawl({"https://example.com/a": "markdown"})
    client = CachedCrawl(inner, tmp_path)

    first = await client.scrape("https://example.com/a")
    await client.scrape("https://example.com/a")

    assert first is not None
    assert first.markdown == "markdown"
    assert len(inner.scrape_calls) == 1


async def test_fresh_bypasses_cache(tmp_path):
    inner = CountingCrawl({"https://example.com/a": "markdown"})
    client = CachedCrawl(inner, tmp_path)

    await client.scrape("https://example.com/a")
    await client.scrape("https://example.com/a", fresh=True)

    assert len(inner.scrape_calls) == 2
    assert inner.scrape_calls[-1] == ("https://example.com/a", True)


async def test_failed_scrape_not_cached(tmp_path):
    inner = CountingCrawl({})
    client = CachedCrawl(inner, tmp_path)

    await client.scrape("https://example.com/missing")
    await client.scrape("https://example.com/missing")

    assert len(inner.scrape_calls) == 2
