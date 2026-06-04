from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.mcp import MCPClient, MCPToolCall, MCPToolResult


@dataclass(frozen=True)
class AgentRuntime:
    manifest: AgentCapabilityManifest
    clients: Mapping[str, MCPClient]
    action_plane: str | None = None
    identity: str | None = None
    agent_name: str | None = None

    async def list_available_tools(self) -> dict[str, list[str]]:
        return {
            server_id: await client.list_tools()
            for server_id, client in self.clients.items()
        }

    async def call_tool(self, call: MCPToolCall) -> MCPToolResult:
        client = self.clients.get(call.server_id)
        if client is None:
            return MCPToolResult(
                content={"message": f"MCP server is unavailable: {call.server_id}"},
                is_error=True,
                error_code="SERVER_UNAVAILABLE",
            )
        return await client.call_tool(call.tool_name, call.arguments)
