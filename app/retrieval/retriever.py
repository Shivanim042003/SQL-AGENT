import psycopg2

import config

from app.retrieval.embeddings import EmbeddingClient


class Retriever:

    def __init__(
        self,
        embedding_client: EmbeddingClient
    ):
        self.embedding_client = embedding_client

    def search(
        self,
        query: str,
        top_k: int = 5
    ) -> list[dict]:

        # Convert the user's question into an embedding
        query_embedding = self.embedding_client.embed([query])[0]

        # Connect to PostgreSQL
        conn = psycopg2.connect(config.DATABASE_URL)
        cur = conn.cursor()

        try:
            cur.execute(
                """
                SELECT
                    source,
                    content,
                    embedding <=> %s::vector AS distance
                FROM document_embeddings
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (
                    str(query_embedding),
                    str(query_embedding),
                    top_k
                )
            )

            rows = cur.fetchall()

            results = []

            for source, content, distance in rows:
                results.append(
                    {
                        "source": source,
                        "content": content,
                        "distance": distance
                    }
                )

            return results

        finally:
            cur.close()
            conn.close()