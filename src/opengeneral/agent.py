from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from opengeneral.mcp import MCPSession, MCPToolResult
from opengeneral.providers import ChatMessage, ChatProvider, ChatRequest, ToolCall
from opengeneral.runtime import AgentRuntime
from opengeneral.skills import AgentSkill

_EMPTY_PROMPT_HINT = "Give me a goal, or type '/tools' to inspect available tools."
_TOOL_LIMIT_MESSAGE = "Stopped after reaching the tool-call limit without a final answer."
_DEFAULT_MAX_ITERATIONS = 10


@dataclass(frozen=True)
class AgentConstruction:
    skills: tuple[AgentSkill, ...]
    assembled_prompt: str


@dataclass(frozen=True)
class GeneralPurposeAgent:
    runtime: AgentRuntime
    construction: AgentConstruction
    provider: ChatProvider
    # Per-agent conversation memory, accumulated across turns (the daemon keeps one
    # GeneralPurposeAgent per running agent, so history persists for the agent's life).
    history: list[ChatMessage] = field(default_factory=list)
    max_iterations: int = _DEFAULT_MAX_ITERATIONS

    async def respond(self, message: str) -> str:
        request = message.strip()
        if request == "/tools":
            return await self._render_tools()
        if request == "/skills":
            return self._render_skills()
        if not request:
            return _EMPTY_PROMPT_HINT

        self.history.append(ChatMessage("user", request))
        async with AsyncExitStack() as stack:
            session = await self._enter_session(stack)
            tools = await session.list_tools() if session is not None else []
            for _ in range(self.max_iterations):
                response = await self.provider.complete(
                    ChatRequest(
                        system=self.construction.assembled_prompt,
                        messages=tuple(self.history),
                        tools=tuple(tools),
                    )
                )
                if not response.tool_calls:
                    content = response.content or ""
                    self.history.append(ChatMessage("assistant", content))
                    return content
                self.history.append(
                    ChatMessage("assistant", response.content, tool_calls=response.tool_calls)
                )
                for call in response.tool_calls:
                    rendered = await self._invoke_tool(session, call)
                    self.history.append(
                        ChatMessage("tool", rendered, tool_call_id=call.id)
                    )
        return _TOOL_LIMIT_MESSAGE

    async def _enter_session(self, stack: AsyncExitStack) -> MCPSession | None:
        # The Action Plane is best-effort: if it is unreachable, the agent still
        # answers from the model, just without tools, rather than failing the turn.
        try:
            return await stack.enter_async_context(self.runtime.action_plane_session())
        except Exception:
            return None

    async def _invoke_tool(self, session: MCPSession | None, call: ToolCall) -> str:
        if session is None:
            return "Action Plane is unavailable; the tool could not be called."
        try:
            result = await session.call_tool(call.name, call.arguments)
        except Exception as error:
            return f"TOOL_ERROR: {error}"
        return self._render_tool_result(result)

    async def _render_tools(self) -> str:
        async with AsyncExitStack() as stack:
            session = await self._enter_session(stack)
            if session is None:
                return "The Action Plane is unavailable."
            tools = await session.list_tools()
            if not tools:
                return "No MCP tools are currently available."
            return "\n".join(f"{tool.name}: {tool.description}" for tool in tools)

    def _render_skills(self) -> str:
        if not self.construction.skills:
            return "No skills are loaded for this persona."
        return "\n".join(
            f"{skill.name}: {skill.description}" for skill in self.construction.skills
        )

    def _render_tool_result(self, result: MCPToolResult) -> str:
        if result.is_error:
            code = result.error_code or "MCP_ERROR"
            return f"{code}: {result.content}"
        return str(result.content)
