from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from opengeneral.action_plane import EmptyActionPlaneConnector
from opengeneral.agent import AgentConstruction, GeneralPurposeAgent
from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.mcp import MCPToolResult
from opengeneral.providers import ChatRequest, ChatResponse, ToolCall, ToolSpec
from opengeneral.runtime import AgentRuntime
from opengeneral.skills import AgentSkill


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[ToolSpec]:
        return [ToolSpec("echo", "Echo input", {"type": "object"})]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        self.calls.append((name, arguments))
        return MCPToolResult(f"{name}: {arguments['text']}")


class FakeConnector:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    @asynccontextmanager
    async def session(self, endpoint: str, identity: str | None):
        yield self._session


class RaisingConnector:
    @asynccontextmanager
    async def session(self, endpoint: str, identity: str | None):
        raise ConnectionError("action plane unreachable")
        yield  # pragma: no cover


class ScriptedProvider:
    def __init__(self, responses: list[ChatResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[ChatRequest] = []

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        return self._responses.pop(0)


class AlwaysToolProvider:
    async def complete(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(content=None, tool_calls=(ToolCall("c", "echo", {"text": "x"}),))


def build_agent(
    provider,
    connector=None,
    construction: AgentConstruction | None = None,
    max_iterations: int = 10,
) -> GeneralPurposeAgent:
    manifest = AgentCapabilityManifest.from_mapping(
        {"id": "org:test/agent:test-v1", "capabilities": []}
    )
    runtime = AgentRuntime(
        manifest=manifest,
        connector=connector or EmptyActionPlaneConnector(),
        endpoint="http://action-plane/mcp",
    )
    return GeneralPurposeAgent(
        runtime,
        construction or AgentConstruction(skills=(), assembled_prompt="Test prompt."),
        provider,
        max_iterations=max_iterations,
    )


async def test_agent_answers_directly_without_tools() -> None:
    provider = ScriptedProvider([ChatResponse("hello there")])
    agent = build_agent(provider)

    response = await agent.respond("hi")

    assert response == "hello there"
    assert provider.requests[0].system == "Test prompt."
    assert [m.role for m in agent.history] == ["user", "assistant"]


async def test_agent_runs_tool_then_returns_final_answer() -> None:
    session = FakeSession()
    provider = ScriptedProvider(
        [
            ChatResponse(content=None, tool_calls=(ToolCall("c1", "echo", {"text": "hi"}),)),
            ChatResponse("done"),
        ]
    )
    agent = build_agent(provider, connector=FakeConnector(session))

    response = await agent.respond("use the echo tool")

    assert response == "done"
    assert session.calls == [("echo", {"text": "hi"})]
    assert [m.role for m in agent.history] == ["user", "assistant", "tool", "assistant"]
    # The tool result is fed back to the model on the second turn.
    second_turn_roles = [m.role for m in provider.requests[1].messages]
    assert "tool" in second_turn_roles
    # Tools discovered from the session are offered to the model.
    assert provider.requests[0].tools[0].name == "echo"


async def test_agent_degrades_to_no_tools_when_action_plane_unreachable() -> None:
    provider = ScriptedProvider([ChatResponse("answer without tools")])
    agent = build_agent(provider, connector=RaisingConnector())

    response = await agent.respond("hi")

    assert response == "answer without tools"
    assert provider.requests[0].tools == ()


async def test_agent_reports_unavailable_action_plane_to_the_model() -> None:
    provider = ScriptedProvider(
        [
            ChatResponse(content=None, tool_calls=(ToolCall("c1", "echo", {"text": "hi"}),)),
            ChatResponse("recovered"),
        ]
    )
    agent = build_agent(provider, connector=RaisingConnector())

    response = await agent.respond("try a tool")

    assert response == "recovered"
    tool_message = next(m for m in agent.history if m.role == "tool")
    assert "unavailable" in tool_message.content.lower()


async def test_agent_stops_at_tool_call_limit() -> None:
    agent = build_agent(
        AlwaysToolProvider(), connector=FakeConnector(FakeSession()), max_iterations=3
    )

    response = await agent.respond("loop forever")

    assert "tool-call limit" in response


async def test_agent_keeps_history_across_turns() -> None:
    provider = ScriptedProvider([ChatResponse("first"), ChatResponse("second")])
    agent = build_agent(provider)

    await agent.respond("one")
    await agent.respond("two")

    # The second request carries the full prior conversation.
    second_request_contents = [m.content for m in provider.requests[1].messages]
    assert "one" in second_request_contents
    assert "first" in second_request_contents
    assert "two" in second_request_contents


async def test_agent_lists_tools_via_introspection() -> None:
    agent = build_agent(ScriptedProvider([]), connector=FakeConnector(FakeSession()))

    response = await agent.respond("/tools")

    assert response == "echo: Echo input"


async def test_agent_lists_skills_from_construction() -> None:
    agent = build_agent(
        ScriptedProvider([]),
        construction=AgentConstruction(
            skills=(AgentSkill("debugging", "Use when diagnosing failures.", "Debug.", __file__),),
            assembled_prompt="Test prompt.",
        ),
    )

    response = await agent.respond("/skills")

    assert response == "debugging: Use when diagnosing failures."


async def test_agent_hints_on_empty_message() -> None:
    response = await build_agent(ScriptedProvider([])).respond("")

    assert response == "Give me a goal, or type '/tools' to inspect available tools."
