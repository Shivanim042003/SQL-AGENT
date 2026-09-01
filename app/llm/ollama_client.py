from ollama import Client

import config
from app.llm.client import LLMClient, LLMResponse


class OllamaClient(LLMClient):

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None
    ):
        self.model = model or config.LLM_MODEL
        self.client = Client(
            host=host or config.OLLAMA_HOST
        )

    def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        think: bool = False
    ) -> LLMResponse:

        ollama_messages = [
            {"role": "system", "content": system},
            *messages
        ]

        response = self.client.chat(
            model=self.model,
            messages=ollama_messages,
            think=think,
            options={
                "num_predict": max_tokens
            }
        )

        return LLMResponse(
            content=response.message.content,
            model=self.model,
            provider="ollama",
            raw=response
        )