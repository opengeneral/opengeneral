from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class MCPToolCall:
    server_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class MCPToolResult:
    content: Any
    is_error: bool = False
    error_code: str | None = None


class MCPClient(Protocol):
    server_id: str

    async def list_tools(self) -> list[str]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult: ...
