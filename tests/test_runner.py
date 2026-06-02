from __future__ import annotations

from io import StringIO

import pytest

from opengeneral.agent import GeneralPurposeAgent
from opengeneral.manifest import AgentCapabilityManifest
from opengeneral.runtime import AgentRuntime
from opengeneral.runner import AgentChatRunner


@pytest.fixture
def runner() -> AgentChatRunner:
    manifest = AgentCapabilityManifest.from_mapping(
        {"id": "org:test/agent:test-v1", "capabilities": []}
    )
    agent = GeneralPurposeAgent(
        AgentRuntime(
            manifest=manifest,
            clients={},
            action_plane="default",
            identity="test-agent",
        )
    )
    return AgentChatRunner("tester", agent)


async def test_chat_exits_on_slash_exit(runner: AgentChatRunner) -> None:
    output = StringIO()

    await runner.chat(StringIO("/exit\n"), output)

    assert "Talking to tester. Type /exit to leave." in output.getvalue()
    assert output.getvalue().endswith("tester> ")


async def test_chat_shows_hint_on_empty_message(runner: AgentChatRunner) -> None:
    output = StringIO()

    await runner.chat(StringIO("\n/exit\n"), output)

    assert "Give me a goal, or type '/tools' to inspect available tools." in output.getvalue()


async def test_chat_forwards_messages_to_agent(runner: AgentChatRunner) -> None:
    output = StringIO()

    await runner.chat(StringIO("hello\n/exit\n"), output)

    assert "I'm ready to work on that: hello" in output.getvalue()


async def test_chat_lists_no_tools_without_action_plane_clients(runner: AgentChatRunner) -> None:
    output = StringIO()

    await runner.chat(StringIO("/tools\n/exit\n"), output)

    assert "No MCP tools are currently available." in output.getvalue()
