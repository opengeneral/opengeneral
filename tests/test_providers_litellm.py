from __future__ import annotations

import json
import sys
import types

from opengeneral.providers import (
    ChatMessage,
    ChatRequest,
    ToolCall,
    ToolSpec,
)
from opengeneral.providers_litellm import (
    _message_to_openai,
    _parse_tool_calls,
    _tool_to_openai,
)


def _fake_tool_call(call_id: str, name: str, arguments: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        id=call_id, function=types.SimpleNamespace(name=name, arguments=arguments)
    )


def test_parse_tool_calls_parses_json_arguments() -> None:
    calls = _parse_tool_calls([_fake_tool_call("c1", "echo", '{"input": "hi"}')])

    assert calls == (ToolCall("c1", "echo", {"input": "hi"}),)


def test_parse_tool_calls_tolerates_bad_json() -> None:
    calls = _parse_tool_calls([_fake_tool_call("c1", "echo", "not json")])

    assert calls[0].arguments == {}


def test_parse_tool_calls_handles_no_calls() -> None:
    assert _parse_tool_calls(None) == ()


def test_tool_spec_serializes_to_openai_function() -> None:
    out = _tool_to_openai(ToolSpec("echo", "Echo input", {"type": "object"}))

    assert out["type"] == "function"
    assert out["function"]["name"] == "echo"
    assert out["function"]["description"] == "Echo input"


def test_assistant_tool_calls_and_tool_results_serialize() -> None:
    assistant = _message_to_openai(
        ChatMessage("assistant", None, tool_calls=(ToolCall("c1", "echo", {"input": "hi"}),))
    )
    assert assistant["tool_calls"][0]["function"]["name"] == "echo"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"input": "hi"}

    tool = _message_to_openai(ChatMessage("tool", "echo: hi", tool_call_id="c1"))
    assert tool == {"role": "tool", "tool_call_id": "c1", "content": "echo: hi"}


async def test_complete_sends_tools_and_parses_tool_calls(monkeypatch) -> None:
    captured: dict = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        message = types.SimpleNamespace(
            content=None, tool_calls=[_fake_tool_call("c1", "echo", '{"input": "hi"}')]
        )
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    fake_litellm = types.ModuleType("litellm")
    fake_litellm.acompletion = fake_acompletion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    from opengeneral.providers_litellm import LiteLLMChatProvider

    provider = LiteLLMChatProvider(model="anthropic/claude", api_key="sk-x", base_url=None)
    response = await provider.complete(
        ChatRequest(
            system="sys",
            messages=(ChatMessage("user", "hi"),),
            tools=(ToolSpec("echo", "Echo input", {"type": "object"}),),
        )
    )

    assert captured["tools"][0]["function"]["name"] == "echo"
    assert captured["tool_choice"] == "auto"
    assert captured["messages"][0] == {"role": "system", "content": "sys"}
    assert response.tool_calls == (ToolCall("c1", "echo", {"input": "hi"}),)
    assert response.content is None
