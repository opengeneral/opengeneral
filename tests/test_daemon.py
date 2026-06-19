from __future__ import annotations

from pathlib import Path

import pytest

from opengeneral.config import (
    ActionPlaneConfig,
    ActionPlanesConfig,
    AgentConfig,
    AgentsConfig,
    KeyConfig,
    KeysConfig,
)
from opengeneral.action_plane import EmptyActionPlaneConnector
from opengeneral.daemon import AgentManager, OpenGeneralDaemon


@pytest.fixture
def isolated_configs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    action_planes_path = tmp_path / "action-planes.json"
    agents_path = tmp_path / "agents.json"
    keys_path = tmp_path / "keys.json"
    monkeypatch.setattr("opengeneral.config.DEFAULT_ACTION_PLANES_CONFIG_PATH", action_planes_path)
    monkeypatch.setattr("opengeneral.config.DEFAULT_AGENTS_CONFIG_PATH", agents_path)
    monkeypatch.setattr("opengeneral.config.DEFAULT_KEYS_CONFIG_PATH", keys_path)
    monkeypatch.setattr("opengeneral.daemon.DEFAULT_ACTION_PLANES_CONFIG_PATH", action_planes_path)
    monkeypatch.setattr("opengeneral.daemon.DEFAULT_AGENTS_CONFIG_PATH", agents_path)
    monkeypatch.setattr("opengeneral.daemon.DEFAULT_KEYS_CONFIG_PATH", keys_path)
    ActionPlanesConfig(
        {"default": ActionPlaneConfig("default", "http://127.0.0.1:4767/mcp")}
    ).write(action_planes_path)
    AgentsConfig({}).write(agents_path)
    KeysConfig(
        {"local-test": KeyConfig("local-test", "static")}
    ).write(keys_path)


async def test_agent_manager_spawns_running_agent(isolated_configs: None) -> None:
    manager = AgentManager()

    result = await manager.spawn(
        AgentConfig("coder", "coder-abc123", "coder", "default", "local-test", "test")
    )

    assert result["name"] == "coder"
    assert result["id"] == "coder-abc123"
    assert result["key"] == "local-test"
    assert result["status"] == "idle"
    assert manager.get_agent("coder")["id"] == "coder-abc123"


async def test_agent_manager_routes_messages_to_running_agent(isolated_configs: None) -> None:
    manager = AgentManager(EmptyActionPlaneConnector())
    await manager.spawn(
        AgentConfig("coder", "coder-abc123", "coder", "default", "local-test", "test")
    )

    result = await manager.send_message("coder", "hello")

    assert result == {"messages": ["I'm ready to work on that."]}


async def test_agent_manager_reports_unknown_agent(isolated_configs: None) -> None:
    manager = AgentManager()

    with pytest.raises(ValueError, match="Agent not found: missing"):
        await manager.send_message("missing", "hello")


async def test_agent_manager_reports_missing_key(isolated_configs: None) -> None:
    manager = AgentManager()

    with pytest.raises(ValueError, match="Key not found: missing"):
        await manager.spawn(
            AgentConfig("coder", "coder-abc123", "coder", "default", "missing", "test")
        )


def test_agent_manager_lists_bundled_personas() -> None:
    personas = AgentManager().list_personas()

    tags = {persona["tag"] for persona in personas}
    assert {"coder", "minimal"} <= tags
    assert all(persona["description"] for persona in personas)


def test_agent_manager_shows_persona_with_capabilities() -> None:
    persona = AgentManager().show_persona("coder")

    assert persona["tag"] == "coder"
    assert persona["agent_id"]
    assert isinstance(persona["capabilities"], list)


def test_agent_manager_reports_unknown_persona() -> None:
    with pytest.raises(ValueError, match="unknown persona: missing"):
        AgentManager().show_persona("missing")


def test_request_shutdown_before_serve_does_not_deadlock() -> None:
    """Shutdown requested before serve_forever should make serve_forever a no-op
    instead of blocking on the never-initialized shutdown event."""
    # port=0 lets the OS assign a free port at bind time, avoiding a probe/bind race.
    daemon = OpenGeneralDaemon("127.0.0.1", 0, AgentManager())
    try:
        daemon.request_shutdown()  # before serve_forever ever runs
        # Should return immediately, not block.
        daemon.serve_forever()
    finally:
        daemon.server_close()


def test_request_shutdown_is_idempotent() -> None:
    daemon = OpenGeneralDaemon("127.0.0.1", 0, AgentManager())
    try:
        daemon.request_shutdown()
        daemon.request_shutdown()  # second call is a no-op, not an error
    finally:
        daemon.server_close()
