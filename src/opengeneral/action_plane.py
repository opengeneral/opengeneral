from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Protocol

from opengeneral.mcp import EmptyMCPSession, MCPSession, MCPToolResult
from opengeneral.providers import ToolSpec

# The Action Plane authenticates the agent identity; OpenGeneral asserts it on every
# connection via this header. The Action Plane is responsible for verifying it.
IDENTITY_HEADER = "X-OpenGeneral-Agent-Id"


class ActionPlaneConnector(Protocol):
    def session(self, endpoint: str, identity: str | None) -> Any:
        """An async context manager yielding a live MCPSession."""
        ...


class EmptyActionPlaneConnector:
    @asynccontextmanager
    async def session(self, endpoint: str, identity: str | None) -> AsyncIterator[MCPSession]:
        yield EmptyMCPSession()


class MCPActionPlaneConnector:
    """Connects to an Action Plane's MCP endpoint over Streamable HTTP."""

    @asynccontextmanager
    async def session(self, endpoint: str, identity: str | None) -> AsyncIterator[MCPSession]:
        # Imported lazily so the daemon (and the no-Action-Plane path) never pay the
        # mcp import cost, and so a frozen binary without an Action Plane works.
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {IDENTITY_HEADER: identity} if identity else None
        async with streamablehttp_client(endpoint, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield _MCPClientSession(session)


class _MCPClientSession:
    def __init__(self, session: Any) -> None:
        self._session = session

    async def list_tools(self) -> list[ToolSpec]:
        result = await self._session.list_tools()
        return [
            ToolSpec(
                name=tool.name,
                description=tool.description or "",
                parameters=tool.inputSchema or {"type": "object", "properties": {}},
            )
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        result = await self._session.call_tool(name, arguments)
        return MCPToolResult(
            content=_render_content(result.content),
            is_error=bool(result.isError),
            error_code="TOOL_ERROR" if result.isError else None,
        )


def _render_content(blocks: Any) -> str:
    """Flatten MCP content blocks into text for feeding back to the LLM."""
    if blocks is None:
        return ""
    parts = []
    for block in blocks:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else str(block))
    return "\n".join(parts)
