from __future__ import annotations

import re
from dataclasses import dataclass

from opengeneral.mcp import MCPToolCall, MCPToolResult
from opengeneral.runtime import AgentRuntime

_TOOL_REQUEST = re.compile(
    r"^use\s+(?P<server_id>\S+)\s+(?P<tool_name>\S+)(?:\s+(?P<payload>.*))?$"
)


@dataclass(frozen=True)
class GeneralPurposeAgent:
    runtime: AgentRuntime

    async def respond(self, message: str) -> str:
        request = message.strip()
        if request == "tools":
            tools = await self.runtime.list_available_tools()
            return "\n".join(
                f"{server_id}: {', '.join(names) if names else '(none)'}"
                for server_id, names in sorted(tools.items())
            )

        match = _TOOL_REQUEST.match(request)
        if match is None:
            return self._reason(request)

        result = await self.runtime.call_tool(
            MCPToolCall(
                server_id=match.group("server_id"),
                tool_name=match.group("tool_name"),
                arguments={"input": match.group("payload") or ""},
            )
        )
        return self._render_tool_result(result)

    def _reason(self, message: str) -> str:
        if not message:
            return "Give me a goal, or type 'tools' to inspect MCP capabilities."
        return f"I can reason about that goal, but environment actions must be requested through MCP: {message}"

    def _render_tool_result(self, result: MCPToolResult) -> str:
        if result.is_error:
            code = result.error_code or "MCP_ERROR"
            return f"{code}: {result.content}"
        return str(result.content)
