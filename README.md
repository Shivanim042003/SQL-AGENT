# SQL Agent

A self-correcting natural-language-to-SQL agent. You ask a question in plain English; the agent writes a PostgreSQL `SELECT`, runs it on a read-only connection, has a second model pass check the result, retries with feedback if the check fails, and returns the answer. It runs fully locally with Ollama.

The bundled dataset is the `thelook` e-commerce data (events, orders, order items, products, users).

## How it works

```
check_intent -> load_schema -> retrieve_context -> generate_sql -> execute_sql -> critique_sql -+-> format_answer
                                                        ^                                       |
                                                        +------------ prepare_retry <-----------+   (max 2 retries)
```

| Node | What it does |
|---|---|
| `check_intent` | LLM check that the request is read-only. Fails closed: if the check itself errors, the request stops. |
| `load_schema` | Reads table and column info from the database. |
| `retrieve_context` | Embedding search over the data dictionary and business glossary (`datasets/thelook`), stored in pgvector. |
| `generate_sql` | Generates one SELECT (JSON output), with SELECT-only checks before anything runs. |
| `execute_sql` | Runs the query on the read-only role with a 15 s timeout. |
| `critique_sql` | A second LLM pass judges whether the SQL answers the question; its feedback drives the retry. Two narrow code shortcuts can accept trivially verifiable counts without the LLM (see below). |
| `format_answer` | Builds the response or the refusal. |

Errors are classified (`SAFETY_BLOCK`, `CRITIC_ERROR`, `SQL_TIMEOUT`, `LLM_ERROR`, `UNKNOWN_ERROR`, ...). Safety blocks, critic errors and unknown errors are not retried.

Each request is also written to `agent_request_metrics` (latencies per node, retry count, error type, `success`). Blocked and failed requests are stored with `success=false`.

## Security model

Three independent layers, each of which must pass:

1. **Intent check** (LLM, fail-closed) refuses destructive requests before any SQL is generated.
2. **Generator checks** only allow a single SELECT statement.
3. **Database roles** enforce it regardless of the model:
   - `app_readonly` runs generated SQL (SELECT only, 15 s statement timeout).
   - `app_retrieval` is used by retrieval and can SELECT only from `document_embeddings`.
   - The owner connection (`DATABASE_URL`) is used for loading data, schema introspection and metrics, never for generated SQL.

Role definitions are in `infra/create_readonly_role.sql` and `infra/create_retrieval_role.sql`. Passwords are supplied at run time (psql variables) and are never committed. Keep credentials in `.env`, which is git-ignored.
## Requirements

- Python 3 environment (conda or venv)
- Docker (for Postgres with pgvector, image `pgvector/pgvector:pg16`)
- [Ollama](https://ollama.com) with these models pulled:
  `ollama pull qwen3:8b` and `ollama pull qwen3-embedding:0.6b`
- Node.js (frontend only)

## Setup

```
pip install -r requirements.txt
pip install -r requirements-dev.txt        # tests
docker compose -f infra/docker-compose.yml up -d
```

Create `.env` in the repo root (see the table below), then, against the database from `DATABASE_URL`:

1. Load the dataset: `python data/loaders/load_data.py`
2. Apply `infra/create_retrieval_table.sql`, then `infra/create_indexes.sql`
3. Build embeddings: `python data/loaders/load_embeddings.py`
4. Create the roles: `infra/create_readonly_role.sql` and `infra/create_retrieval_role.sql` (each documents how to pass its password), and put the resulting URLs in `.env`
5. Check the schema: `python data/loaders/verify_schema.py`

Start the API:

```
python -m uvicorn app.api:app --port 8000
```

`POST http://127.0.0.1:8000/api/query` with `{"question": "How many events are there?"}`.

Frontend (React + Vite, expects the API on `127.0.0.1:8000`):

```
cd frontend
npm install
npm run dev
```

## Configuration

| Variable | Purpose |
|---|---|
| `ACTIVE_DATASET` | Dataset folder under `datasets/` (default `thelook`). |
| `LLM_PROVIDER`, `LLM_MODEL` | Chat model provider and name (default `ollama`, `qwen3:8b`). |
| `INTENT_MODEL` | Optional separate model for the intent check; defaults to `LLM_MODEL`. |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | Embedding provider and model (`qwen3-embedding:0.6b`). |
| `OLLAMA_HOST` | Default `http://127.0.0.1:11434`. Use the IP, not `localhost`: on Windows `localhost` added about 2 s to every new connection. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Used by Docker Compose to create the database. |
| `DATABASE_URL` | Owner connection: data loading, schema info, metrics. |
| `READONLY_DATABASE_URL` | `app_readonly` connection used to execute generated SQL. |
| `RETRIEVAL_DATABASE_URL` | `app_retrieval` connection. Required; retrieval refuses to start without it. |
| `SKIP_CRITIC_FOR_SIMPLE_COUNTS` | `1` enables the two critic shortcuts below. Default off. |

Ollama setting that matters for speed: `OLLAMA_NUM_PARALLEL=2`. With one slot, every request paid about 4 s to switch between the short intent prompt and the long generator prompt; two slots removed most of it. The Ollama Windows install reads it from the user environment variables.

Two more Ollama settings reduce the overhead around long prompts: `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0`. On the author's iGPU they made simple questions that use the critic about 20% faster (roughly 2.5-4.7 s each) and the summed median about 7% faster; retried and multi-step questions did not change. With them on, the repeated eval (5 trials) still passed 50/50, answered-question latency was p50 12.8 s / p90 23.8 s, and the red-team set passed. A quantized KV cache can change model output slightly, so re-run the evals after changing these.
## Critic shortcuts (opt-in)

When `SKIP_CRITIC_FOR_SIMPLE_COUNTS=1`, the LLM critic is skipped in exactly two cases (`app/agent/fast_path.py`):

- Question "How many `<table>` are there?" and SQL `SELECT COUNT(*) FROM <that table>`, with a single integer result.
- Question "How many sessions contain/have/include/with a `<x>` event?" and SQL `SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type = '<x>'` with the same `<x>`, a single integer result above 0 and no execution error.

Both are covered by tests, including negative cases. Anything else goes to the LLM critic.

## Tests and evaluation

```
python -m pytest -q                    # 42 unit tests
python eval/run_golden_eval.py         # 10 questions: easy, medium, hard, safety
python eval/run_red_team.py            # 12 adversarial / destructive requests
python eval/run_repeated_eval.py --trials 5   # pass rate and p50/p90 latency over repeated runs
```

The unit tests need no database or Ollama: `conftest.py` loads `.env` if present and otherwise supplies placeholder `DATABASE_URL` and `READONLY_DATABASE_URL` values.

The golden eval checks answers against ground truth computed from the database. On the author's machine (Intel Arc iGPU, Vulkan, qwen3:8b) the current `main` scores 10/10 on the golden eval and 12/12 on the red-team set. Typical latency: plain COUNT(*) questions that take the shortcut about 3-8 s; other questions about 11-23 s, mostly spent processing the 1.5-2k-token generator and critic prompts on the iGPU. Questions that need a retry take 25-30 s. A retry costs roughly 10-20 s more. A repeated run (5 trials of all 10 questions, `eval/run_repeated_eval.py`) passed 50/50 with answered-question latency p50 13.2 s and p90 23.2 s; one question (`medium_03`) needed a retry in 3 of 5 trials.

## Limitations

Please read these before trusting the numbers above.

- **Small, partly tuned evaluation.** The golden set has 10 questions and the red-team set has 12. Some prompt sections and shortcuts were written while debugging these same questions, so the scores overstate general accuracy.
- **Hardcoded shortcuts.** `deterministic_sql` shortcuts and exact-SQL acceptance rules in `critic_node.py` (for a plain distinct-session count and the conversion-rate query) would accept those exact queries without asking the model. In the recorded runs they did not trigger, because the generator's SQL carries column aliases and so does not match, and the LLM critic judged those questions. The two opt-in critic shortcuts above are narrower and tested, but they are still special cases.
- **An 8B critic is unreliable.** It sometimes rejects correct SQL (for example, `COUNT(DISTINCT session_id) ... WHERE event_type = 'purchase'` for "sessions that contain a purchase event"). Prompt wording did not fix this; the code shortcut does for that shape only.
- **Generator first attempts vary.** For some questions the first SQL is wrong and is fixed on retry, which is the main source of slow answers.
- **Single dataset, single statement.** Only one dataset is configured, and only one SELECT is allowed per request.
- **Development defaults.** The Docker Compose file publishes Postgres on port 5432 on all interfaces and passes the whole `.env` to the database container. Do not expose it beyond a development machine as-is.
- **Metrics use the owner connection** rather than a dedicated metrics role.
- **The frontend hardcodes `127.0.0.1:8000`.**