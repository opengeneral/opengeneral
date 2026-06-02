from __future__ import annotations

from opengeneral.action_plane import EmptyActionPlaneConnector


async def test_empty_action_plane_connector_returns_no_clients() -> None:
    connector = EmptyActionPlaneConnector()

    clients = await connector.connect("http://127.0.0.1:4767/mcp", "coder-abc123")

    assert clients == {}
