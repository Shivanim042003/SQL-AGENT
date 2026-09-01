import config

from app.retrieval.embeddings import EmbeddingClient
from app.retrieval.ollama_embeddings import OllamaEmbeddingClient


def get_embedding_client() -> EmbeddingClient:
    provider = config.EMBEDDING_PROVIDER.lower()

    if provider == "ollama":
        return OllamaEmbeddingClient()

    raise ValueError(
        f"Unknown embedding provider: {config.EMBEDDING_PROVIDER}"
    )