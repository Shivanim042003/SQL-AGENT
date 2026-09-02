import sys
from pathlib import Path

import psycopg2

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

import config
from app.retrieval.chunker import chunk_markdown
from app.retrieval.factory import get_embedding_client


DOCUMENT_FILES = [
    config.DATASET_DIR / "data_dictionary.md",
    config.DATASET_DIR / "business_glossary.md",
]


def load_embeddings() -> None:
    """Chunk knowledge documents, embed them, and store them in PostgreSQL."""

    print("=" * 80)
    print("THELOOK EMBEDDING LOADER")
    print("=" * 80)

    # Collect chunks from all knowledge documents
    chunks = []

    for file_path in DOCUMENT_FILES:
        print(f"\nChunking: {file_path.name}")

        file_chunks = chunk_markdown(file_path)

        print(f"Found {len(file_chunks)} chunks.")

        chunks.extend(file_chunks)

    print(f"\nTotal chunks: {len(chunks)}")

    # Create embedding client
    print("\nInitializing embedding client...")
    client = get_embedding_client()

    # Extract chunk text
    texts = [chunk["content"] for chunk in chunks]

    print("Generating embeddings...")
    embeddings = client.embed(texts)

    # Safety check
    if len(embeddings) != len(chunks):
        raise ValueError(
            f"Expected {len(chunks)} embeddings, "
            f"but received {len(embeddings)}."
        )

    print(f"Generated {len(embeddings)} embeddings.")

    # Connect to PostgreSQL
    conn = psycopg2.connect(config.DATABASE_URL)
    cur = conn.cursor()

    try:
        # Rebuild retrieval data
        print("\nClearing existing embeddings...")

        cur.execute("DELETE FROM document_embeddings;")

        # Insert chunks and embeddings
        print("Storing embeddings in PostgreSQL...")

        for chunk, embedding in zip(chunks, embeddings):

            cur.execute(
                """
                INSERT INTO document_embeddings (
                    source,
                    content,
                    embedding
                )
                VALUES (%s, %s, %s::vector);
                """,
                (
                    chunk["source"],
                    chunk["content"],
                    str(embedding)
                )
            )

        conn.commit()

        print(
            f"\nSuccessfully stored "
            f"{len(chunks)} document embeddings."
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

        print("Database connection closed.")


if __name__ == "__main__":
    load_embeddings()