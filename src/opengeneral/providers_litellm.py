from __future__ import annotations

from opengeneral.providers import ChatRequest, ChatResponse


class LiteLLMChatProvider:
    def __init__(self, model: str, api_key: str, base_url: str | None = None) -> None:
        from litellm import acompletion

        self.acompletion = acompletion
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    async def complete(self, request: ChatRequest) -> ChatResponse:
        kwargs: dict[str, object] = {"api_key": self.api_key}
        if self.base_url is not None:
            kwargs["api_base"] = self.base_url
        response = await self.acompletion(
            model=self.model,
            messages=[
                {"role": "system", "content": request.system},
                *[
                    {"role": message.role, "content": message.content}
                    for message in request.messages
                ],
            ],
            **kwargs,
        )
        return ChatResponse(response.choices[0].message.content or "")
