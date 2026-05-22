from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.mcp import MCPToolCall, MCPToolResult
from opengeneral.runtime import AgentRuntime


@dataclass(frozen=True)
class FakeMCPClient:
    server_id: str

    async def list_tools(self) -> list[str]:
        return ["echo"]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult({"name": name, "arguments": arguments})


def manifest(capabilities: list[dict[str, Any]] | None = None) -> AgentCapabilityManifest:
    return AgentCapabilityManifest.from_mapping(
        {"id": "org:test/agent:test-v1", "capabilities": capabilities or []}
    )


async def test_runtime_does_not_gate_declared_capabilities_on_action_identity() -> None:
    runtime = AgentRuntime(
        manifest=manifest(
            [
                {
                    "id": "files_editing",
                    "description": "Can inspect and modify files in the workspace.",
                }
            ]
        ),
        clients={},
        action_plane=None,
        identity=None,
    )

    assert await runtime.list_available_tools() == {}


async def test_runtime_routes_tool_calls_to_mcp_client() -> None:
    client = FakeMCPClient("local-filesystem")
    runtime = AgentRuntime(
        manifest=manifest(),
        clients={client.server_id: client},
        action_plane=None,
        identity=None,
    )

    result = await runtime.call_tool(
        MCPToolCall(client.server_id, "echo", {"input": "hello"})
    )

    assert result == MCPToolResult(
        {"name": "echo", "arguments": {"input": "hello"}}
    )


async def test_runtime_reports_unavailable_server_as_mcp_error() -> None:
    runtime = AgentRuntime(manifest=manifest(), clients={}, action_plane=None, identity=None)

    result = await runtime.call_tool(
        MCPToolCall("local-shell", "run", {"input": "pwd"})
    )

    assert result.is_error is True
    assert result.error_code == "SERVER_UNAVAILABLE"
