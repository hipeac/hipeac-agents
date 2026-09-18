"""Crawl service: provider-agnostic web fetch and search.

Nodes depend on :class:`CrawlClient`, never on Firecrawl directly, so the
provider can be swapped in the factory without touching agent logic. The
default provider uses the official Firecrawl Python SDK over its plain API.
"""

import asyncio
from typing import Any, Protocol, runtime_checkable

from hipeac_agents import settings
from hipeac_agents.services.types import ScrapeResult, SearchHit
from hipeac_agents.services.urls import normalize_url
from hipeac_agents.storage import cache as json_cache


@runtime_checkable
class CrawlClient(Protocol):
    """What nodes may do against the open web: scrape one URL, search the web.

    Runtime-checkable so a provider class can be asserted against it in tests:
    a missing method here is an ``AttributeError`` at harvest time, swallowed
    by the per-source error handling into a nondescript failed outcome.
    """

    async def scrape(self, url: str, fresh: bool = False) -> ScrapeResult | None:
        """Fetch a single URL and return its markdown content.

        :param url: The URL to scrape.
        :param fresh: Bypass the cache and fetch anew.
        """
        ...

    async def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        """Search the open web and return the hits."""
        ...

    async def fetch_feed(self, url: str) -> str | None:
        """Fetch a raw RSS/Atom document.

        :param url: The feed URL.
        :returns: The raw XML text, or ``None`` when the fetch fails.
        """
        ...


class ScrapeQuotaError(Exception):
    """Raised when the crawl provider has no credits left for the request."""


def _page_title(document: Any) -> str:
    metadata = getattr(document, "metadata", None)
    return (getattr(metadata, "title", "") or "") if metadata else ""


def _page_url(document: Any) -> str:
    metadata = getattr(document, "metadata", None)
    return (getattr(metadata, "sourceURL", None) or getattr(metadata, "url", "") or "") if metadata else ""


def _page_published_at(document: Any) -> str | None:
    metadata = getattr(document, "metadata", None)
    published = getattr(metadata, "published_time", None) if metadata else None
    return published or None


def _status_code(document: Any) -> int | None:
    metadata = getattr(document, "metadata", None)
    return getattr(metadata, "statusCode", None) if metadata else None


async def fetch_feed_direct(url: str) -> str | None:
    """Fetch a raw RSS/Atom document over plain HTTP.

    Feeds are deterministic XML — no browser rendering needed, so they never
    go through Firecrawl. A plain GET with a browser-ish User-Agent suffices;
    failures return ``None`` and the caller falls back to page scraping.

    Provider-independent by nature, so every crawl client shares this one
    implementation rather than declaring its own.

    :param url: The feed URL.
    :returns: The raw XML text, or ``None`` when the fetch fails.
    """
    import urllib.request

    def _get() -> str | None:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "hipeac-vision-watch/0.1"})  # noqa: S310 — feed URLs come from operator config
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 — feed URLs come from operator config
                return response.read().decode("utf-8", errors="replace")
        except Exception:
            return None

    return await asyncio.to_thread(_get)


class FirecrawlCrawl:
    """Crawl provider backed by the official Firecrawl SDK (plain API)."""

    def __init__(self, firecrawl_client: Any) -> None:
        """Wrap an already-constructed Firecrawl client.

        :param firecrawl_client: A ``firecrawl.v2.FirecrawlClient`` instance.
        """
        self._client = firecrawl_client

    async def scrape(self, url: str, fresh: bool = False) -> ScrapeResult | None:
        """Fetch a single URL and return its markdown content.

        :param url: The URL to scrape.
        :param fresh: Unused here; the cache wrapper handles freshness.
        :returns: The scrape result, or ``None`` when the URL does not resolve
            or the scrape fails.
        """
        try:
            document = await asyncio.to_thread(self._client.scrape, url, formats=["markdown"], only_main_content=True)
        except Exception as exc:
            if "Insufficient credits" in str(exc) or type(exc).__name__ == "PaymentRequiredError":
                raise ScrapeQuotaError(str(exc)) from exc
            return None

        if not getattr(document, "markdown", None):
            return None

        return ScrapeResult(
            url=_page_url(document) or url,
            title=_page_title(document),
            markdown=document.markdown,
            status_code=_status_code(document),
            published_at=_page_published_at(document),
        )

    async def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        """Search the web and return normalised hits.

        :param query: The search query.
        :param limit: Maximum number of results.
        :returns: The search hits, empty when the search fails.
        """
        try:
            data = await asyncio.to_thread(self._client.search, query, limit=limit)
        except Exception:
            return []

        results: list[Any] = []

        for section in ("web", "news", "all"):
            value = getattr(data, section, None)
            if isinstance(value, list):
                results.extend(value)

        hits = []

        for item in results:
            url = getattr(item, "url", None)
            if not url:
                continue
            hits.append(
                SearchHit(
                    url=url,
                    title=getattr(item, "title", "") or "",
                    description=getattr(item, "description", "") or "",
                    markdown=getattr(item, "markdown", "") or "",
                )
            )

        return hits[:limit]

    async def fetch_feed(self, url: str) -> str | None:
        """Fetch a raw RSS/Atom document; a plain GET, not a Firecrawl call.

        :param url: The feed URL.
        :returns: The raw XML text, or ``None`` when the fetch fails.
        """
        return await fetch_feed_direct(url)


class CachedCrawl:
    """Crawl wrapper that caches scrape results on the local filesystem.

    Keyed by the SHA-256 of the URL; the markdown of every scraped page is
    kept on disk, so repeat runs and in-run repeat fetches (newsletter URL
    resolution, verification gates) don't pay for the same page twice. The
    re-sample check passes ``fresh=True`` — its point is a fresh fetch.
    """

    def __init__(self, client: CrawlClient, cache_root: str) -> None:
        """Wrap a crawl client with a file cache.

        :param client: The crawl client to wrap.
        :param cache_root: Directory the cache lives under.
        """
        self._client = client
        self._cache_root = cache_root

    async def scrape(self, url: str, fresh: bool = False) -> ScrapeResult | None:
        """Fetch one URL, from cache unless asked for a fresh fetch.

        :param url: The URL to scrape.
        :param fresh: Bypass the cache and fetch anew.
        :returns: The scrape result, or ``None`` when the scrape fails.
        """
        path = json_cache.sharded_path(self._cache_root, "scrapes", normalize_url(url))

        if not fresh and (cached := json_cache.cache_get(path)):
            return ScrapeResult.model_validate(cached["payload"])

        result = await self._client.scrape(url, fresh=True)

        if result is not None:
            json_cache.cache_put(path, result.model_dump(mode="json"))

        return result

    async def search(self, query: str, limit: int = 5) -> list[SearchHit]:
        """Search the web; pass-through to the wrapped client.

        :param query: The search query.
        :param limit: Maximum number of results.
        :returns: The search hits, empty when the search fails.
        """
        return await self._client.search(query, limit=limit)

    async def fetch_feed(self, url: str) -> str | None:
        """Fetch a feed; pass-through to the wrapped client, never cached.

        The cache exists to avoid paying twice for the same page. A feed is
        free to fetch and its whole point is what changed since last time, so
        a cached copy would serve last week's entries to this week's window.

        :param url: The feed URL.
        :returns: The raw XML text, or ``None`` when the fetch fails.
        """
        return await self._client.fetch_feed(url)


def load_crawl_client() -> CrawlClient | None:
    """Build the configured crawl provider, or ``None`` when unconfigured.

    :returns: A ``CrawlClient`` if ``FIRECRAWL_API_KEY`` is set, else ``None``.
    """
    if not settings.FIRECRAWL_API_KEY:
        return None

    from firecrawl.v2 import FirecrawlClient

    return FirecrawlCrawl(FirecrawlClient(api_key=settings.FIRECRAWL_API_KEY, api_url=settings.FIRECRAWL_API_URL))
