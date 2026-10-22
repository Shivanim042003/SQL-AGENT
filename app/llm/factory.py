import config

from app.llm.client import LLMClient
from app.llm.ollama_client import OllamaClient


def get_llm_client(model: str | None = None) -> LLMClient:
    provider = config.LLM_PROVIDER.lower()

    if provider == "ollama":
        return OllamaClient(model=model)

    if provider == "anthropic":
        raise NotImplementedError(
            "Anthropic provider is planned but not implemented yet."
        )

    raise ValueError(
        f"Unknown LLM provider: {config.LLM_PROVIDER}"
    )