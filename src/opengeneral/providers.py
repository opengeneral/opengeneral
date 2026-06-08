from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ChatRequest:
    system: str
    messages: tuple[ChatMessage, ...]


@dataclass(frozen=True)
class ChatResponse:
    content: str


class ChatProvider(Protocol):
    async def complete(self, request: ChatRequest) -> ChatResponse: ...


@dataclass(frozen=True)
class StaticChatProvider:
    response: str = "I'm ready to work on that."

    async def complete(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(self.response)
