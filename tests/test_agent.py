from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opengeneral.agent import AgentConstruction, GeneralPurposeAgent
from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.mcp import MCPToolResult
from opengeneral.providers import ChatRequest, ChatResponse
from opengeneral.runtime import AgentRuntime
from opengeneral.skills import AgentSkill


@dataclass(frozen=True)
class FakeMCPClient:
    server_id: str

    async def list_tools(self) -> list[str]:
        return ["echo"]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult(f"{name}: {arguments['input']}")


class FakeProvider:
    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        return ChatResponse(f"provider: {request.messages[-1].content}")


def agent(
    construction: AgentConstruction | None = None,
    provider: FakeProvider | None = None,
) -> GeneralPurposeAgent:
    manifest = AgentCapabilityManifest.from_mapping(
        {"id": "org:test/agent:test-v1", "capabilities": []}
    )
    client = FakeMCPClient("local-test")
    return GeneralPurposeAgent(
        AgentRuntime(
            manifest=manifest,
            clients={client.server_id: client},
            action_plane=None,
            identity=None,
        ),
        construction or AgentConstruction(skills=(), assembled_prompt="Test prompt."),
        provider or FakeProvider(),
    )


async def test_agent_lists_tools_through_runtime() -> None:
    response = await agent().respond("/tools")

    assert response == "local-test: echo"


async def test_agent_lists_skills_from_construction() -> None:
    response = await agent(
        AgentConstruction(
            skills=(
                AgentSkill(
                    "debugging",
                    "Use when diagnosing failures.",
                    "Debug carefully.",
                    __file__,
                ),
            ),
            assembled_prompt="Test prompt.",
        )
    ).respond("/skills")

    assert response == "debugging: Use when diagnosing failures."


async def test_agent_uses_mcp_for_requested_tool_call() -> None:
    response = await agent().respond("use local-test echo hello")

    assert response == "echo: hello"


async def test_agent_uses_provider_for_normal_messages() -> None:
    provider = FakeProvider()

    response = await agent(provider=provider).respond("plan a refactor")

    assert response == "provider: plan a refactor"
    assert provider.requests[0].system == "Test prompt."


async def test_agent_uses_default_empty_message_hint() -> None:
    response = await agent().respond("")

    assert response == "Give me a goal, or type '/tools' to inspect available tools."
