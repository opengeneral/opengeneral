from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opengeneral.agent import GeneralPurposeAgent
from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.mcp import MCPToolResult
from opengeneral.runtime import AgentRuntime


@dataclass(frozen=True)
class FakeMCPClient:
    server_id: str

    async def list_tools(self) -> list[str]:
        return ["echo"]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult(f"{name}: {arguments['input']}")


def agent() -> GeneralPurposeAgent:
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
        )
    )


async def test_agent_lists_tools_through_runtime() -> None:
    response = await agent().respond("/tools")

    assert response == "local-test: echo"


async def test_agent_uses_mcp_for_requested_tool_call() -> None:
    response = await agent().respond("use local-test echo hello")

    assert response == "echo: hello"


async def test_agent_keeps_general_reasoning_internal() -> None:
    response = await agent().respond("plan a refactor")

    assert response == "I'm ready to work on that: plan a refactor"
