from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ToolSpec:
    """An LLM-facing description of a callable tool (an MCP tool, flattened)."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatMessage:
    # "user" / "assistant" / "tool". The system prompt is carried by ChatRequest.
    role: Literal["user", "assistant", "tool"]
    content: str | None = None
    # Set on assistant turns that request tools.
    tool_calls: tuple[ToolCall, ...] = ()
    # Set on tool-result turns to bind the result to the originating call.
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ChatRequest:
    system: str
    messages: tuple[ChatMessage, ...]
    tools: tuple[ToolSpec, ...] = ()


@dataclass(frozen=True)
class ChatResponse:
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


class ChatProvider(Protocol):
    async def complete(self, request: ChatRequest) -> ChatResponse: ...


@dataclass(frozen=True)
class StaticChatProvider:
    response: str = "I'm ready to work on that."

    async def complete(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(self.response)
