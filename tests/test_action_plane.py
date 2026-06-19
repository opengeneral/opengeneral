from __future__ import annotations

import socket
import threading
import time

import pytest

from opengeneral.action_plane import EmptyActionPlaneConnector, MCPActionPlaneConnector


async def test_empty_action_plane_connector_yields_empty_session() -> None:
    connector = EmptyActionPlaneConnector()

    async with connector.session("http://127.0.0.1:4767/mcp", "coder-abc123") as session:
        assert await session.list_tools() == []
        result = await session.call_tool("echo", {"input": "hi"})
        assert result.is_error is True
        assert result.error_code == "NO_ACTION_PLANE"


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def fake_action_plane():
    """A real MCP server (FastMCP over Streamable HTTP) acting as a local Action Plane."""
    import uvicorn
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("fake-action-plane")

    @server.tool()
    def echo(text: str) -> str:
        return f"echo: {text}"

    port = _free_port()
    config = uvicorn.Config(
        server.streamable_http_app(), host="127.0.0.1", port=port, log_level="error"
    )
    uvicorn_server = uvicorn.Server(config)
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()

    deadline = time.time() + 10
    while time.time() < deadline and not uvicorn_server.started:
        time.sleep(0.05)
    assert uvicorn_server.started, "fake MCP server did not start"

    yield f"http://127.0.0.1:{port}/mcp"

    uvicorn_server.should_exit = True
    thread.join(timeout=10)


async def test_mcp_connector_lists_and_calls_tools(fake_action_plane: str) -> None:
    connector = MCPActionPlaneConnector()

    async with connector.session(fake_action_plane, "coder-abc123") as session:
        tools = await session.list_tools()
        assert "echo" in {tool.name for tool in tools}

        result = await session.call_tool("echo", {"text": "hi"})
        assert result.is_error is False
        assert "echo: hi" in result.content
