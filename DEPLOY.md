# Deploying on Render (free)

Layout: static UI + FastAPI API on Render, Postgres (pgvector) on Neon, hosted LLM (Groq) and embeddings (Google Gemini).
Free-tier caveats: the API sleeps after 15 min idle (about 1 min to wake), has 512 MB RAM, and Neon free storage is 1 GB.
Hosted models differ from the local qwen3:8b, so re-run the evals (step 6) before trusting results.

## 1. Accounts and keys
- Neon: create a project, then a database named `sql_agent`. Copy the **direct** (non-pooled) connection string.
- Groq: create an API key. The blueprint uses `openai/gpt-oss-120b` (on the free plan: 30 requests/min, 1K requests/day, 8K tokens/min, 200K tokens/day). Models on the free list change; check Groq's Rate Limits page.
- Google AI Studio (aistudio.google.com/apikey): create a free API key for embeddings. `gemini-embedding-001` returns 3072 numbers; the client truncates to 1024 and re-normalises to match `vector(1024)`. Note: on the free tier Google may use prompts to improve its products, so questions typed into the demo go to Google.

## 2. Prepare the database (from the repo folder)
Use the Neon owner URL as `DATABASE_URL` in a **separate** env file or shell session, not your local `.env`:

```
$env:DATABASE_URL = "<neon owner url>"
python data/loaders/load_data.py
psql $env:DATABASE_URL -f infra/create_retrieval_table.sql
psql $env:DATABASE_URL -f infra/create_indexes.sql
psql $env:DATABASE_URL -f infra/create_metrics_table.sql
```

The full dataset may exceed 1 GB. Check with `select pg_size_pretty(pg_database_size(current_database()))`; if it does not fit, load a subset first (for example fewer rows per table).

## 3. Embeddings with the hosted model
Vectors from different models are not compatible, so rebuild them with the same provider the API will use:

```
$env:EMBEDDING_PROVIDER = "openai_compatible"
$env:EMBEDDING_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
$env:EMBEDDING_MODEL = "gemini-embedding-001"
$env:EMBEDDING_DIMENSIONS = "1024"
$env:EMBEDDING_API_KEY = "<google key>"
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
`LLM_API_KEY`, `EMBEDDING_API_KEY` (Google key), `DATABASE_URL`, `READONLY_DATABASE_URL`, `RETRIEVAL_DATABASE_URL`, `CORS_ORIGINS` (the UI URL, no trailing slash), and on the UI service `VITE_API_URL` (the API URL).
Deploy the API first, then set `VITE_API_URL` and deploy the UI.

## 6. Verify
- `GET <api>/api/health` returns ok.
- Run the golden and red-team evals against the hosted model (locally, with the hosted env vars set).
- Free-tier budget: a question costs about 4K tokens, or 10K+ if it retries, against 8K tokens/min and 200K/day, so expect about 2 questions/min and 40-50/day. The defaults (`RATE_LIMIT_PER_MINUTE=2`, `DAILY_REQUEST_CAP=40`) reflect that; a 429 from the provider shows as a failed request.
- Abuse limits: `RATE_LIMIT_PER_MINUTE` (per client) and `DAILY_REQUEST_CAP` (global) protect the free LLM quota. State is in memory, so it resets on restart.
