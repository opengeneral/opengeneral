from __future__ import annotations

import pytest

from opengeneral.agent_factory import create_agent
from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.personas import AgentPersona
from opengeneral.providers import StaticChatProvider
from opengeneral.runtime import AgentRuntime


def persona() -> AgentPersona:
    manifest = AgentCapabilityManifest.from_mapping(
        {"id": "opengeneral/persona:test-v1", "capabilities": []}
    )
    return AgentPersona("tester", __file__, manifest)


def test_create_agent_requires_runtime_agent_name() -> None:
    runtime = AgentRuntime(
        manifest=persona().manifest,
        action_plane="default",
        identity="tester-abc123",
    )

    with pytest.raises(ValueError, match="agent_name is required"):
        create_agent(persona(), runtime, StaticChatProvider())


def test_create_agent_uses_runtime_agent_name_in_prompt() -> None:
    runtime = AgentRuntime(
        manifest=persona().manifest,
        action_plane="default",
        identity="tester-abc123",
        agent_name="friendly-name",
    )

    agent = create_agent(persona(), runtime, StaticChatProvider())

    assert "Your name is friendly-name." in agent.construction.assembled_prompt
    assert "You are operating as a tester agent." in agent.construction.assembled_prompt
