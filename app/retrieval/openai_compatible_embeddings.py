"""Embedding client for OpenAI-compatible /embeddings APIs (Mistral, OpenAI, ...)."""

import httpx

import config
from app.retrieval.embeddings import EmbeddingClient


class OpenAICompatibleEmbeddingClient(EmbeddingClient):

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        dimensions: int | None = None,
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
    ):
        self.model = model or config.EMBEDDING_MODEL
        self.base_url = (base_url or config.EMBEDDING_BASE_URL).rstrip("/")
        self.api_key = api_key or config.EMBEDDING_API_KEY
        self.dimensions = dimensions or config.EMBEDDING_DIMENSIONS

        if not self.api_key:
            raise ValueError(
                "EMBEDDING_API_KEY is not set (required for the hosted embedding provider)."
            )

        self.http = http_client or httpx.Client(timeout=timeout)

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": texts}

        response = self.http.post(
            f"{self.base_url}/embeddings",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Embedding API error {response.status_code}: {response.text[:200]}"
            )

        items = sorted(response.json()["data"], key=lambda d: d.get("index", 0))
        vectors = [item["embedding"] for item in items]

        if self.dimensions:
            for vector in vectors:
                if len(vector) != self.dimensions:
                    raise ValueError(
                        f"Embedding has {len(vector)} dimensions, expected "
                        f"{self.dimensions} (document_embeddings is vector({self.dimensions}))."
                    )

        return vectors
