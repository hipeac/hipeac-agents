"""Vision service: read-only access to HiPEAC Vision knowledge.

The only MCP-backed service: ``hipeac-mcp`` exposes its data exclusively over
MCP, and this repo never touches the ``hipeac-redux`` database directly. Nodes
depend on :class:`VisionClient`, never on the MCP connection itself.
"""

from typing import Any, Protocol

from hipeac_agents import mcp_clients


class VisionClient(Protocol):
    """What nodes may do against Vision knowledge: search and overview reads."""

    async def search_vision(self, query: str, year: int | None = None) -> str:
        """Search the published Vision for relevant content."""
        ...

    async def get_vision_overview(self, year: int | None = None) -> str:
        """Get the Vision overview (chapter structure) as text."""
        ...


class HipeacMcpVision:
    """Vision provider backed by ``hipeac-mcp``'s read-only tools."""

    def __init__(self, tools: list[Any]) -> None:
        """Bind the already-scoped ``hipeac-mcp`` tools.

        :param tools: The langchain tools loaded by ``mcp_clients.load_vision_tools``.
        """
        self._tools = {tool.name: tool for tool in tools}

    async def _invoke(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)

        if tool is None:
            return ""

        result = await tool.ainvoke(args)
        return result if isinstance(result, str) else str(result)

    async def search_vision(self, query: str, year: int | None = None) -> str:
        """Search the published Vision for content relevant to a query.

        :param query: The natural-language query.
        :param year: Optional Vision edition year; defaults to the latest.
        :returns: The search result text; empty when the tool is unavailable.
        """
        args = {"query": query, **({"year": year} if year else {})}
        return await self._invoke("search_vision", args)

    async def get_vision_overview(self, year: int | None = None) -> str:
        """Get the Vision's overview (chapter structure) as text.

        :param year: Optional Vision edition year; defaults to the latest.
        :returns: The overview text; empty when the tool is unavailable.
        """
        args = {"year": year} if year else {}
        return await self._invoke("get_vision_overview", args)


async def load_vision_client() -> VisionClient | None:
    """Build the configured Vision provider, or ``None`` when unconfigured.

    :returns: A ``VisionClient`` if ``HIPEAC_MCP_URL`` is set, else ``None``.
    """
    tools = await mcp_clients.load_vision_tools()

    if not tools:
        return None

    return HipeacMcpVision(tools)
