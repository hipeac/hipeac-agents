"""Tests for the service layer (SDK boundaries mocked, never live)."""

from types import SimpleNamespace

from hipeac_agents.services.crawl import CachedCrawl, CrawlClient, FirecrawlCrawl, fetch_feed_direct
from hipeac_agents.services.mail import AgentMailMail, markdown_to_html


class FakeFirecrawlSdk:
    """Fake of ``firecrawl.v2.FirecrawlClient`` — boundary, not logic."""

    def __init__(self, *, document=None, search_data=None, error=None):
        self.document = document
        self.search_data = search_data
        self.error = error
        self.scrape_calls = []
        self.search_calls = []

    def scrape(self, url, **kwargs):
        self.scrape_calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.document

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        if self.error:
            raise self.error
        return self.search_data


def fake_document(markdown="# Title\n\nBody text.", title="Example headline", url="https://example.com/a"):
    return SimpleNamespace(
        markdown=markdown,
        metadata=SimpleNamespace(title=title, sourceURL=url, statusCode=200),
    )


class TestFirecrawlScrape:
    async def test_scrape_returns_normalised_result(self):
        sdk = FakeFirecrawlSdk(document=fake_document())
        crawl = FirecrawlCrawl(sdk)

        result = await crawl.scrape("https://example.com/a")

        assert result.title == "Example headline"
        assert result.url == "https://example.com/a"
        assert "Body text." in result.markdown
        assert result.status_code == 200
        assert sdk.scrape_calls[0][1]["formats"] == ["markdown"]

    async def test_scrape_failure_returns_none(self):
        crawl = FirecrawlCrawl(FakeFirecrawlSdk(error=RuntimeError("boom")))

        assert await crawl.scrape("https://example.com/404") is None

    async def test_scrape_empty_markdown_returns_none(self):
        crawl = FirecrawlCrawl(FakeFirecrawlSdk(document=fake_document(markdown="")))

        assert await crawl.scrape("https://example.com/a") is None


class FakeSearchItem:
    def __init__(self, url, title, description=""):
        self.url = url
        self.title = title
        self.description = description
        self.markdown = ""


class TestFirecrawlSearch:
    async def test_search_returns_normalised_hits(self):
        sdk = FakeFirecrawlSdk(
            search_data=SimpleNamespace(
                web=[
                    FakeSearchItem("https://example.com/1", "First", "desc"),
                    FakeSearchItem("https://example.com/2", "Second", ""),
                ],
                news=None,
                all=None,
            )
        )
        crawl = FirecrawlCrawl(sdk)

        hits = await crawl.search("humanoids industrial deployment", limit=2)

        assert [h.url for h in hits] == ["https://example.com/1", "https://example.com/2"]
        assert hits[0].title == "First"

    async def test_search_failure_returns_empty(self):
        crawl = FirecrawlCrawl(FakeFirecrawlSdk(error=RuntimeError("rate limit")))

        assert await crawl.search("anything") == []


class FakeResponse:
    """Minimal stand-in for what ``urllib.request.urlopen`` returns."""

    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self) -> bytes:
        return self.payload


FEED_XML = b"<rss><channel><item><link>https://example.com/a</link></item></channel></rss>"


class TestCrawlProtocol:
    """Every shipped provider must satisfy the protocol nodes call against.

    A missing method surfaces as an ``AttributeError`` inside a gathered task
    and is swallowed into a nondescript failed source outcome, so the suite
    has to assert conformance rather than wait for a harvest to reveal it.
    """

    def test_firecrawl_provider_implements_the_protocol(self):
        assert isinstance(FirecrawlCrawl(FakeFirecrawlSdk()), CrawlClient)

    def test_cache_wrapper_implements_the_protocol(self, tmp_path):
        assert isinstance(CachedCrawl(FirecrawlCrawl(FakeFirecrawlSdk()), str(tmp_path)), CrawlClient)


class TestFeedFetch:
    async def test_returns_the_raw_document(self, monkeypatch):
        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResponse(FEED_XML))

        assert await fetch_feed_direct("https://example.com/feed.xml") == FEED_XML.decode()

    async def test_failure_returns_none(self, monkeypatch):
        import urllib.request

        def boom(*args, **kwargs):
            raise OSError("connection refused")

        monkeypatch.setattr(urllib.request, "urlopen", boom)

        assert await fetch_feed_direct("https://example.com/feed.xml") is None

    async def test_provider_fetches_the_feed_without_the_sdk(self, monkeypatch):
        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResponse(FEED_XML))
        sdk = FakeFirecrawlSdk()

        xml = await FirecrawlCrawl(sdk).fetch_feed("https://example.com/feed.xml")

        assert xml == FEED_XML.decode()
        assert not sdk.scrape_calls  # A feed costs no Firecrawl credit.

    async def test_cache_wrapper_never_caches_a_feed(self, monkeypatch, tmp_path):
        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResponse(FEED_XML))
        inner = FirecrawlCrawl(FakeFirecrawlSdk())
        calls: list[str] = []

        async def counting_fetch(url: str) -> str | None:
            calls.append(url)
            return FEED_XML.decode()

        monkeypatch.setattr(inner, "fetch_feed", counting_fetch)
        crawl = CachedCrawl(inner, str(tmp_path))

        await crawl.fetch_feed("https://example.com/feed.xml")
        await crawl.fetch_feed("https://example.com/feed.xml")

        # A cached feed would serve last week's entries into this week's window.
        assert len(calls) == 2


class FakeAgentMailSdk:
    """Fake of ``agentmail.AgentMail`` — boundary, not logic."""

    def __init__(self):
        self.sent = []
        messages = SimpleNamespace(
            list=lambda inbox_id, **kwargs: SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        inbox_id=inbox_id,
                        message_id="m1",
                        from_=SimpleNamespace(email="board@example.com"),
                        subject="A tip",
                        preview="Look at this",
                        timestamp=None,
                        created_at=None,
                    )
                ]
            ),
            get=lambda inbox_id, message_id: SimpleNamespace(text="full body text"),
            send=self._send,
        )
        self.inboxes = SimpleNamespace(messages=messages)

    def _send(self, inbox_id, to, subject, text, html=None, reply_to=None, **kwargs):
        self.sent.append((inbox_id, to, subject, text, html, reply_to))
        return SimpleNamespace(message_id="m-out-1")


class TestAgentMailMail:
    async def test_list_messages_normalises_fields(self):
        mail = AgentMailMail(FakeAgentMailSdk())

        messages = await mail.list_messages("vision-news")

        assert messages[0].message_id == "m1"
        assert messages[0].from_ == "board@example.com"
        assert messages[0].subject == "A tip"

    async def test_list_messages_failure_returns_empty(self, monkeypatch):
        mail = AgentMailMail(FakeAgentMailSdk())

        def boom(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(mail._client.inboxes.messages, "list", boom)
        assert await mail.list_messages("vision-news") == []

    async def test_send_returns_message_id(self):
        sdk = FakeAgentMailSdk()
        mail = AgentMailMail(sdk)

        message_id = await mail.send("vision-news", "news@example.com", "Digest", "# Digest")

        assert message_id == "m-out-1"
        assert sdk.sent == [("vision-news", "news@example.com", "Digest", "# Digest", None, None)]

    async def test_send_forwards_html_and_reply_to(self):
        sdk = FakeAgentMailSdk()
        mail = AgentMailMail(sdk)

        await mail.send(
            "vision-news",
            "news@example.com",
            "Digest",
            "# Digest",
            html="<h1>Digest</h1>",
            reply_to="webmaster@example.com",
        )

        assert sdk.sent[0][4] == "<h1>Digest</h1>"
        assert sdk.sent[0][5] == "webmaster@example.com"

    async def test_get_message_text(self):
        mail = AgentMailMail(FakeAgentMailSdk())

        assert await mail.get_message_text("vision-news", "m1") == "full body text"


class TestMarkdownToHtml:
    def test_renders_digest_structure(self):
        html = markdown_to_html("## One big thing\n\n**_Lead._** — [arxiv.org](https://arxiv.org/abs/1)\n")

        assert "<h2>One big thing</h2>" in html
        assert "<strong><em>Lead.</em></strong>" in html
        assert '<a href="https://arxiv.org/abs/1">arxiv.org</a>' in html

    def test_wraps_in_a_standalone_document(self):
        html = markdown_to_html("# Digest")

        assert html.startswith("<!doctype html>")
        assert html.endswith("</body></html>")

    def test_leaves_no_raw_markdown_markers(self):
        html = markdown_to_html("# Digest\n\n- _item_ — text\n")

        assert "# Digest" not in html
        assert "- _item_" not in html
