import config

from app.retrieval.embeddings import EmbeddingClient
from app.retrieval.ollama_embeddings import OllamaEmbeddingClient
from app.retrieval.openai_compatible_embeddings import OpenAICompatibleEmbeddingClient


def get_embedding_client() -> EmbeddingClient:
    provider = config.EMBEDDING_PROVIDER.lower()

    if provider == "ollama":
        return OllamaEmbeddingClient()

    if provider == "openai_compatible":
        return OpenAICompatibleEmbeddingClient()

    raise ValueError(
        f"Unknown embedding provider: {config.EMBEDDING_PROVIDER}"
    )