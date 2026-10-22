"""Embedding client for OpenAI-compatible /embeddings APIs (Gemini, OpenAI, ...)."""

import math
import time

import httpx

import config
from app.retrieval.embeddings import EmbeddingClient

_RETRY_STATUSES = {429, 500, 502, 503, 504}
BATCH_SIZE = 50


class OpenAICompatibleEmbeddingClient(EmbeddingClient):
    """
    If EMBEDDING_DIMENSIONS is set, vectors must end up with exactly that
    length. A longer vector is truncated and re-normalised, which is valid for
    Matryoshka-trained models (e.g. gemini-embedding-001: 3072 -> 1024).
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        dimensions: int | None = None,
        timeout: float = 60.0,
        max_attempts: int = 4,
        http_client: httpx.Client | None = None,
    ):
        self.model = model or config.EMBEDDING_MODEL
        self.base_url = (base_url or config.EMBEDDING_BASE_URL).rstrip("/")
        self.api_key = api_key or config.EMBEDDING_API_KEY
        self.dimensions = dimensions or config.EMBEDDING_DIMENSIONS
        self.max_attempts = max_attempts

        if not self.api_key:
            raise ValueError(
                "EMBEDDING_API_KEY is not set (required for the hosted embedding provider)."
            )

        self.http = http_client or httpx.Client(timeout=timeout)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []

        for start in range(0, len(texts), BATCH_SIZE):
            vectors.extend(self._embed_batch(texts[start:start + BATCH_SIZE]))

        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = None

        for attempt in range(1, self.max_attempts + 1):
            response = self.http.post(
                f"{self.base_url}/embeddings",
                json={"model": self.model, "input": texts},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

            if response.status_code not in _RETRY_STATUSES:
                break

            if attempt < self.max_attempts:
                time.sleep(min(2.0 ** attempt * 2, 30.0))

        if response.status_code >= 400:
            raise RuntimeError(
                f"Embedding API error {response.status_code}: {response.text[:200]}"
            )

        items = sorted(response.json()["data"], key=lambda d: d.get("index", 0))
        vectors = [self._fit(item["embedding"]) for item in items]

        if len(vectors) != len(texts):
            raise ValueError(
                f"Expected {len(texts)} embeddings, received {len(vectors)}."
            )

        return vectors

    def _fit(self, vector: list[float]) -> list[float]:
        if not self.dimensions or len(vector) == self.dimensions:
            return vector

        if len(vector) < self.dimensions:
            raise ValueError(
                f"Embedding has {len(vector)} dimensions, expected "
                f"{self.dimensions} (document_embeddings is vector({self.dimensions}))."
            )

        cut = vector[: self.dimensions]
        norm = math.sqrt(sum(x * x for x in cut)) or 1.0
        return [x / norm for x in cut]
