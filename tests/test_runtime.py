from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from opengeneral.action_plane import EmptyActionPlaneConnector
from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.mcp import MCPToolResult
from opengeneral.providers import ToolSpec
from opengeneral.runtime import AgentRuntime


def manifest(capabilities: list[dict[str, Any]] | None = None) -> AgentCapabilityManifest:
    return AgentCapabilityManifest.from_mapping(
        {"id": "org:test/agent:test-v1", "capabilities": capabilities or []}
    )


class FakeSession:
    async def list_tools(self) -> list[ToolSpec]:
        return [ToolSpec("echo", "Echo input", {"type": "object"})]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult({"name": name, "arguments": arguments})


class RecordingConnector:
    def __init__(self) -> None:
        self.opened_with: tuple[str, str | None] | None = None

    @asynccontextmanager
    async def session(self, endpoint: str, identity: str | None):
        self.opened_with = (endpoint, identity)
        yield FakeSession()


async def test_runtime_yields_empty_session_without_action_plane() -> None:
    runtime = AgentRuntime(manifest=manifest(), connector=EmptyActionPlaneConnector())

    async with runtime.action_plane_session() as session:
        assert await session.list_tools() == []


async def test_runtime_opens_session_via_connector_with_endpoint_and_identity() -> None:
    connector = RecordingConnector()
    runtime = AgentRuntime(
        manifest=manifest(),
        connector=connector,
        endpoint="http://127.0.0.1:4767/mcp",
        identity="coder-abc123",
    )

    async with runtime.action_plane_session() as session:
        tools = await session.list_tools()

    assert connector.opened_with == ("http://127.0.0.1:4767/mcp", "coder-abc123")
    assert [tool.name for tool in tools] == ["echo"]
