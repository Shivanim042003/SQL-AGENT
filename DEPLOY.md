# Deploying on Render (free)

Layout: static UI + FastAPI API on Render, Postgres (pgvector) on Neon, hosted LLM (Groq) and embeddings (Mistral).
Free-tier caveats: the API sleeps after 15 min idle (about 1 min to wake), has 512 MB RAM, and Neon free storage is 1 GB.
Hosted models differ from the local qwen3:8b, so re-run the evals (step 6) before trusting results.

## 1. Accounts and keys
- Neon: create a project, then a database named `sql_agent`. Copy the **direct** (non-pooled) connection string.
- Groq: create an API key; pick a chat model ID from their console (set as `LLM_MODEL`).
- Mistral: create an API key (embeddings use `mistral-embed`, 1024 dimensions, matching `vector(1024)`).

## 2. Prepare the database (from the repo folder)
Use the Neon owner URL as `DATABASE_URL` in a **separate** env file or shell session, not your local `.env`:

```
$env:DATABASE_URL = "<neon owner url>"
python data/loaders/load_data.py
psql $env:DATABASE_URL -f infra/create_retrieval_table.sql
psql $env:DATABASE_URL -f infra/create_indexes.sql
```

The full dataset may exceed 1 GB. Check with `select pg_size_pretty(pg_database_size(current_database()))`; if it does not fit, load a subset first (for example fewer rows per table).

## 3. Embeddings with the hosted model
Vectors from different models are not compatible, so rebuild them with the same provider the API will use:

```
$env:EMBEDDING_PROVIDER = "openai_compatible"
$env:EMBEDDING_BASE_URL = "https://api.mistral.ai/v1"
$env:EMBEDDING_MODEL = "mistral-embed"
$env:EMBEDDING_DIMENSIONS = "1024"
$env:EMBEDDING_API_KEY = "<mistral key>"
python data/loaders/load_embeddings.py
```

## 4. Roles
```
psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -v ro_password="<pw1>" -f infra/create_readonly_role.sql
psql $env:DATABASE_URL -v ON_ERROR_STOP=1 -v retr_password="<pw2>" -f infra/create_retrieval_role.sql
```
Build `READONLY_DATABASE_URL` and `RETRIEVAL_DATABASE_URL` from the Neon host with those roles and passwords (add `?sslmode=require`).

## 5. Render
Push to GitHub, then Render > New > Blueprint > pick the repo. Fill the `sync: false` variables:
`LLM_MODEL`, `LLM_API_KEY`, `EMBEDDING_API_KEY`, `DATABASE_URL`, `READONLY_DATABASE_URL`, `RETRIEVAL_DATABASE_URL`, `CORS_ORIGINS` (the UI URL, no trailing slash), and on the UI service `VITE_API_URL` (the API URL).
Deploy the API first, then set `VITE_API_URL` and deploy the UI.

## 6. Verify
- `GET <api>/api/health` returns ok.
- Run the golden and red-team evals against the hosted model (locally, with the hosted env vars set).
- Abuse limits: `RATE_LIMIT_PER_MINUTE` (per client) and `DAILY_REQUEST_CAP` (global) protect the free LLM quota. State is in memory, so it resets on restart.
