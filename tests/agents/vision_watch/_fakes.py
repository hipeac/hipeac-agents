"""Shared fakes for the vision-watch agent tests.

Fakes implement the service protocols and the LLM runner interface used by
the nodes — the boundary, not the logic.
"""

from pydantic import BaseModel

from hipeac_agents.services.types import MailMessage, ScrapeResult, SearchHit


class FakeStructuredOutput:
    """Fake of ``llm.with_structured_output(schema)``."""

    def __init__(self, fake_llm, schema):
        self._fake_llm = fake_llm
        self._schema = schema

    async def ainvoke(self, prompt: str):
        return await self._fake_llm.ainvoke(self._schema, prompt)


class FakeLLM:
    """Scripted LLM: maps a schema type to a fixed response object.

    ``with_structured_output`` returns a runner whose ``ainvoke`` resolves the
    registered handler, recording every prompt it was asked about.
    """

    def __init__(self, handlers: dict[type, object] | None = None):
        self.handlers = handlers or {}
        self.calls: list[tuple[type, str]] = []

    def with_structured_output(self, schema):
        return FakeStructuredOutput(self, schema)

    async def ainvoke(self, schema, prompt: str):
        self.calls.append((schema, prompt))
        if schema is str:
            return "In brief text."
        if getattr(schema, "__name__", "") == "InBrief":
            return schema(text="In brief text.")
        handler = self.handlers.get(schema)
        if handler is None:
            raise AssertionError(f"no scripted handler for {schema.__name__}")
        return handler(prompt) if callable(handler) else handler


class FakeCrawl:
    """Fake of ``CrawlClient``: canned scrape results, search hits, feeds."""

    def __init__(
        self,
        pages: dict[str, str] | None = None,
        missing: set[str] | None = None,
        search_hits=None,
        feeds: dict[str, str] | None = None,
    ):
        self.pages = pages or {}
        self.missing = missing or set()
        self.search_hits = search_hits or []
        self.feeds = feeds or {}
        self.scrape_calls = []
        self.search_calls = []
        self.feed_calls = []

    async def scrape(self, url: str, fresh: bool = False):
        self.scrape_calls.append(url)
        if url in self.missing or url not in self.pages:
            return None
        return ScrapeResult(url=url, title=self.pages[url][0], markdown=self.pages[url][1])

    async def search(self, query: str, limit: int = 5):
        self.search_calls.append(query)
        if self.search_hits:
            return self.search_hits[:limit]
        return [SearchHit(url=f"https://example.com/{i}", title=query) for i in range(limit)]

    async def fetch_feed(self, url: str) -> str | None:
        self.feed_calls.append(url)
        return self.feeds.get(url)


class FakeMail:
    """Fake of ``MailClient``: canned inbox messages and send capture."""

    def __init__(self, messages: list[MailMessage] | None = None, bodies: dict[str, str] | None = None):
        self.messages = messages or []
        self.bodies = bodies or {}
        self.sent = []

    async def list_messages(self, inbox_id: str, after=None, before=None):
        return [m for m in self.messages if m.inbox_id == inbox_id]

    async def get_message_text(self, inbox_id: str, message_id: str) -> str:
        return self.bodies.get(message_id, "")

    async def send(self, inbox_id: str, to, subject: str, text: str, html=None, reply_to=None) -> str:
        self.sent.append((inbox_id, to, subject, text, html, reply_to))
        return "m-sent"


def make_candidate_handler(items: list[dict]) -> callable:
    """Build a CandidateList handler for the extraction judgement call."""
    from hipeac_agents.agents.vision_watch.nodes.harvest.models import CandidateList

    return lambda prompt: CandidateList.model_validate({"items": items})


def make_gate_handler(theme_ids: list[str], tier: int = 2, matches: bool = True, datapoint: str = "") -> callable:
    """Build a GateVerdict handler for the merged verification gate."""
    from hipeac_agents.agents.vision_watch.nodes.harvest.models import GateVerdict

    return lambda prompt: GateVerdict.model_validate(
        {"theme_ids": theme_ids, "tier": tier, "title_matches": matches, "datapoint": datapoint}
    )


def make_grouping_handler(assignments: list[dict]) -> callable:
    """Build a GroupingPlan handler for the grouping-bar judgement call."""
    from hipeac_agents.agents.vision_watch.nodes.cluster import GroupingPlan

    return lambda prompt: GroupingPlan.model_validate({"assignments": assignments})


def structured_model(cls: type[BaseModel], **data) -> BaseModel:
    return cls.model_validate(data)
