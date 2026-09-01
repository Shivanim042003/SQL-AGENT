from ollama import Client

import config
from app.retrieval.embeddings import EmbeddingClient


class OllamaEmbeddingClient(EmbeddingClient):

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None
    ):
        self.model = model or config.EMBEDDING_MODEL
        self.client = Client(host=host or config.OLLAMA_HOST)

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embed(
            model=self.model,
            input=texts
        )

        return response.embeddings