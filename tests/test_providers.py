from __future__ import annotations

import pytest

from opengeneral.config import KeyConfig
from opengeneral.provider_factory import create_provider
from opengeneral.providers import ChatMessage, ChatRequest, StaticChatProvider


async def test_static_provider_returns_configured_response() -> None:
    provider = StaticChatProvider("hello")

    response = await provider.complete(ChatRequest("system", (ChatMessage("user", "hi"),)))

    assert response.content == "hello"


def test_provider_factory_rejects_unknown_provider_type() -> None:
    with pytest.raises(ValueError, match="Unknown provider type"):
        create_provider(KeyConfig("bad", "missing"), "secret", "model")
