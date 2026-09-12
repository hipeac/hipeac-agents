"""Service-layer wiring: build configured clients for a run.

This is the only place providers are chosen. Agents receive protocol-typed
clients; swapping a provider later is a change here plus a factory function,
never a change to agent logic.
"""

from dataclasses import dataclass

from hipeac_agents.services.crawl import CrawlClient, load_crawl_client
from hipeac_agents.services.mail import MailClient, load_mail_client
from hipeac_agents.services.vision import VisionClient, load_vision_client


@dataclass(frozen=True)
class Services:
    """The service clients a run was wired with; ``None`` means skipped."""

    crawl: CrawlClient | None
    mail: MailClient | None
    vision: VisionClient | None


def load_services() -> Services:
    """Build the plain-API service clients (crawl, mail).

    Each service is independent: an unset API key yields ``None`` and the
    consuming node reports the affected sources as blocked instead.

    :returns: The wired :class:`Services` without the MCP-backed client.
    """
    return Services(crawl=load_crawl_client(), mail=load_mail_client(), vision=None)


async def load_services_async() -> Services:
    """Build the configured service clients, including the MCP-backed one.

    :returns: The wired :class:`Services`.
    """
    return Services(
        crawl=load_crawl_client(),
        mail=load_mail_client(),
        vision=await load_vision_client(),
    )
