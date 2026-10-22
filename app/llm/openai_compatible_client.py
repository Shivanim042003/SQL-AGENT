"""Chat client for any OpenAI-compatible /chat/completions API (Groq, Cerebras, OpenRouter, ...)."""

import logging
import re
import time

import httpx

import config
from app.llm.client import LLMClient, LLMResponse

logger = logging.getLogger(__name__)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)

# Statuses worth retrying: rate limit and transient server errors.
_RETRY_STATUSES = {429, 500, 502, 503, 504}


class OpenAICompatibleClient(LLMClient):

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        max_attempts: int = 3,
        http_client: httpx.Client | None = None,
    ):
        self.model = model or config.LLM_MODEL
        self.base_url = (base_url or config.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key or config.LLM_API_KEY
        self.max_attempts = max_attempts

        if not self.api_key:
            raise ValueError(
                "LLM_API_KEY is not set (required for the hosted LLM provider)."
            )

        self.http = http_client or httpx.Client(timeout=timeout)

    def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1024,
        think: bool = False,  # accepted for interface parity; ignored
    ) -> LLMResponse:

        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/chat/completions"

        started = time.perf_counter()
        response = None

        for attempt in range(1, self.max_attempts + 1):
            response = self.http.post(url, json=payload, headers=headers)

            if response.status_code not in _RETRY_STATUSES:
                break

            if attempt < self.max_attempts:
                delay = _retry_delay(response, attempt)
                logger.warning(
                    "llm_retry | status=%s | attempt=%s | sleeping=%.1fs",
                    response.status_code, attempt, delay,
                )
                time.sleep(delay)

        if response.status_code >= 400:
            raise RuntimeError(
                f"LLM API error {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        content = data["choices"][0]["message"].get("content") or ""
        content = _THINK_BLOCK.sub("", content).strip()

        logger.info(
            "llm_call | model=%s | wall=%.2fs | usage=%s",
            self.model,
            time.perf_counter() - started,
            data.get("usage"),
        )

        return LLMResponse(
            content=content,
            model=self.model,
            provider="openai_compatible",
            raw=data,
        )


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return min(float(retry_after), 10.0)
        except ValueError:
            pass
    return min(2.0 ** attempt, 10.0)
