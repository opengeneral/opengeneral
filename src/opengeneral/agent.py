from __future__ import annotations

import re
from dataclasses import dataclass

from opengeneral.mcp import MCPToolCall, MCPToolResult
from opengeneral.runtime import AgentRuntime
from opengeneral.skills import AgentSkill

_TOOL_REQUEST = re.compile(
    r"^use\s+(?P<server_id>\S+)\s+(?P<tool_name>\S+)(?:\s+(?P<payload>.*))?$"
)
_EMPTY_PROMPT_HINT = "Give me a goal, or type '/tools' to inspect available tools."
_READY_PREFIX = "I'm ready to work on that"


@dataclass(frozen=True)
class AgentConstruction:
    skills: tuple[AgentSkill, ...]
    assembled_prompt: str


@dataclass(frozen=True)
class GeneralPurposeAgent:
    runtime: AgentRuntime
    construction: AgentConstruction

    async def respond(self, message: str) -> str:
        request = message.strip()
        if request == "/tools":
            tools = await self.runtime.list_available_tools()
            if not tools:
                return "No MCP tools are currently available."
            return "\n".join(
                f"{server_id}: {', '.join(names) if names else '(none)'}"
                for server_id, names in sorted(tools.items())
            )
        if request == "/skills":
            return self._render_skills()

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
            return _EMPTY_PROMPT_HINT
        return f"{_READY_PREFIX}: {message}"

    def _render_skills(self) -> str:
        if not self.construction.skills:
            return "No skills are loaded for this persona."
        return "\n".join(
            f"{skill.name}: {skill.description}"
            for skill in self.construction.skills
        )

    def _render_tool_result(self, result: MCPToolResult) -> str:
        if result.is_error:
            code = result.error_code or "MCP_ERROR"
            return f"{code}: {result.content}"
        return str(result.content)
