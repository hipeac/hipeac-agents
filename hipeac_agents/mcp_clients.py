"""The one place ``MultiServerMCPClient`` is constructed.

Nodes never import this module; they receive service clients wired by
``services/factory.py``. Only the ``hipeac`` MCP server remains here — crawl
and mail use plain provider APIs via the official SDKs.
"""

from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from hipeac_agents import settings


VISION_TOOLS = ("search_vision", "get_vision_overview", "get_vision_article")


async def load_vision_tools() -> list[Any]:
    """Load the read-only Vision tools from ``hipeac-mcp``.

    :returns: The scoped tool list; empty when ``HIPEAC_MCP_URL`` is unset
        (the connector is skipped) or the connection fails.
    """
    if not settings.HIPEAC_MCP_URL:
        return []

    try:
        client = MultiServerMCPClient(
            {
                "hipeac": {
                    "url": settings.HIPEAC_MCP_URL,
                    "transport": "streamable_http",
                }
            }
        )
        tools = await client.get_tools()
    except Exception:
        return []

    return [tool for tool in tools if tool.name in VISION_TOOLS]
