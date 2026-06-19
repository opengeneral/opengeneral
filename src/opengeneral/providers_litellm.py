from __future__ import annotations

import json
from typing import Any

from opengeneral.providers import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ToolCall,
    ToolSpec,
)


class LiteLLMChatProvider:
    def __init__(self, model: str, api_key: str, base_url: str | None = None) -> None:
        from litellm import acompletion

        self.acompletion = acompletion
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    async def complete(self, request: ChatRequest) -> ChatResponse:
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url is not None:
            kwargs["api_base"] = self.base_url
        if request.tools:
            kwargs["tools"] = [_tool_to_openai(tool) for tool in request.tools]
            kwargs["tool_choice"] = "auto"

        response = await self.acompletion(
            model=self.model,
            messages=[
                {"role": "system", "content": request.system},
                *[_message_to_openai(message) for message in request.messages],
            ],
            **kwargs,
        )
        message = response.choices[0].message
        return ChatResponse(
            content=message.content or None,
            tool_calls=_parse_tool_calls(getattr(message, "tool_calls", None)),
        )


def _tool_to_openai(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters or {"type": "object", "properties": {}},
        },
    }


def _message_to_openai(message: ChatMessage) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": message.content or "",
        }
    payload: dict[str, Any] = {"role": message.role, "content": message.content or ""}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in message.tool_calls
        ]
    return payload


def _parse_tool_calls(raw: Any) -> tuple[ToolCall, ...]:
    if not raw:
        return ()
    calls = []
    for call in raw:
        raw_args = call.function.arguments or "{}"
        try:
            arguments = json.loads(raw_args)
        except (TypeError, json.JSONDecodeError):
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {"value": arguments}
        calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
    return tuple(calls)
