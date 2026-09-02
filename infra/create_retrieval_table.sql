CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS document_embeddings;

CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1024) NOT NULL
);