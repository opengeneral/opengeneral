from __future__ import annotations

from opengeneral.config import SUPPORTED_PROVIDER_TYPES, KeyConfig
from opengeneral.providers import ChatProvider, StaticChatProvider
from opengeneral.providers_litellm import LiteLLMChatProvider


def create_provider(key: KeyConfig, secret: str, model: str) -> ChatProvider:
    if key.provider_type == "static":
        return StaticChatProvider()
    if key.provider_type in SUPPORTED_PROVIDER_TYPES:
        return LiteLLMChatProvider(model=model, api_key=secret, base_url=key.base_url)
    raise ValueError(f"Unknown provider type: {key.provider_type}")
