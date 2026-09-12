"""Service layer: provider-agnostic clients for crawl, mail, and Vision.

Nodes depend on the protocols in this package, never on providers directly.
The factory builds the configured providers from environment variables; each
service is independently skippable (``None`` when unconfigured).
"""

from .crawl import CrawlClient, FirecrawlCrawl, load_crawl_client  # noqa: F401
from .mail import AgentMailMail, MailClient, load_mail_client  # noqa: F401
from .types import MailMessage, ScrapeResult, SearchHit  # noqa: F401
from .vision import HipeacMcpVision, VisionClient, load_vision_client  # noqa: F401


__all__ = [
    "AgentMailMail",
    "CrawlClient",
    "FirecrawlCrawl",
    "HipeacMcpVision",
    "MailClient",
    "MailMessage",
    "ScrapeResult",
    "SearchHit",
    "VisionClient",
    "load_crawl_client",
    "load_mail_client",
    "load_vision_client",
]
