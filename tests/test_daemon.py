from __future__ import annotations

from pathlib import Path

import pytest

from opengeneral.config import (
    ActionPlaneConfig,
    ActionPlanesConfig,
    AgentConfig,
    AgentsConfig,
)
from opengeneral.daemon import AgentManager


@pytest.fixture
def isolated_configs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    action_planes_path = tmp_path / "action-planes.json"
    agents_path = tmp_path / "agents.json"
    monkeypatch.setattr("opengeneral.config.DEFAULT_ACTION_PLANES_CONFIG_PATH", action_planes_path)
    monkeypatch.setattr("opengeneral.config.DEFAULT_AGENTS_CONFIG_PATH", agents_path)
    monkeypatch.setattr("opengeneral.daemon.DEFAULT_ACTION_PLANES_CONFIG_PATH", action_planes_path)
    monkeypatch.setattr("opengeneral.daemon.DEFAULT_AGENTS_CONFIG_PATH", agents_path)
    ActionPlanesConfig(
        {"default": ActionPlaneConfig("default", "http://127.0.0.1:4767/mcp")}
    ).write(action_planes_path)
    AgentsConfig({}).write(agents_path)


async def test_agent_manager_spawns_running_agent(isolated_configs: None) -> None:
    manager = AgentManager()

    result = await manager.spawn(AgentConfig("coder", "coder-abc123", "coder", "default"))

    assert result["name"] == "coder"
    assert result["id"] == "coder-abc123"
    assert result["status"] == "idle"
    assert manager.get_agent("coder")["id"] == "coder-abc123"


async def test_agent_manager_routes_messages_to_running_agent(isolated_configs: None) -> None:
    manager = AgentManager()
    await manager.spawn(AgentConfig("coder", "coder-abc123", "coder", "default"))

    result = await manager.send_message("coder", "hello")

    assert result == {"messages": ["I'm ready to work on that: hello"]}


async def test_agent_manager_reports_unknown_agent(isolated_configs: None) -> None:
    manager = AgentManager()

    with pytest.raises(ValueError, match="Agent not found: missing"):
        await manager.send_message("missing", "hello")
