import logging
import time

from ollama import Client

import config
from app.llm.client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


def _seconds(response, field: str) -> float:
    return (getattr(response, field, None) or 0) / 1e9


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

        started = time.perf_counter()

        response = self.client.chat(
            model=self.model,
            messages=ollama_messages,
            think=think,
            options={
                "num_predict": max_tokens
            }
        )

        wall = time.perf_counter() - started
        logger.info(
            "llm_call | model=%s | wall=%.2fs | server_total=%.2fs | load=%.2fs | "
            "prefill=%.2fs (%s tok) | decode=%.2fs (%s tok)",
            self.model,
            wall,
            _seconds(response, "total_duration"),
            _seconds(response, "load_duration"),
            _seconds(response, "prompt_eval_duration"),
            getattr(response, "prompt_eval_count", None),
            _seconds(response, "eval_duration"),
            getattr(response, "eval_count", None),
        )

        return LLMResponse(
            content=response.message.content,
            model=self.model,
            provider="ollama",
            raw=response
        )