from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from opengeneral.providers import ToolSpec


@dataclass(frozen=True)
class MCPToolResult:
    content: Any
    is_error: bool = False
    error_code: str | None = None


class MCPSession(Protocol):
    """A live connection to an Action Plane's MCP server, scoped to one agent turn."""

    async def list_tools(self) -> list[ToolSpec]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult: ...


class EmptyMCPSession:
    """The session used when no Action Plane is configured: no tools, no calls."""

    async def list_tools(self) -> list[ToolSpec]:
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult(
            content=f"No Action Plane is configured, so tool '{name}' is unavailable.",
            is_error=True,
            error_code="NO_ACTION_PLANE",
        )
