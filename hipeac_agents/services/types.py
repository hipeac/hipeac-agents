"""Service-layer data types shared by providers and nodes.

Generic plumbing types (scrape results, mail messages); domain literals live
in the agents' schema modules.
"""

from datetime import datetime

from pydantic import BaseModel


class ScrapeResult(BaseModel):
    """The markdown content of one scraped page."""

    url: str
    title: str = ""
    markdown: str = ""
    status_code: int | None = None
    published_at: str | None = None


class SearchHit(BaseModel):
    """One result from a web search."""

    url: str
    title: str = ""
    description: str = ""
    markdown: str = ""


class MailMessage(BaseModel):
    """One email message in an inbox."""

    inbox_id: str
    message_id: str
    from_: str = ""
    to: list[str] = []
    subject: str = ""
    text: str = ""
    preview: str = ""
    timestamp: datetime | None = None
    created_at: datetime | None = None
