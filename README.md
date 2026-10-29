# SQL Agent

A self-correcting natural-language-to-SQL agent. You ask a question in plain English; the agent writes a PostgreSQL `SELECT`, runs it on a read-only connection, has a second model pass review the database result, retries with feedback when that critic rejects the query, and returns the result. The critic is a model judgment, not proof of correctness (it can reject good SQL and accept bad SQL; the ablation below measures how often). It runs fully locally with Ollama, and a hosted free-tier demo is described in `DEPLOY.md`.

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
   - `app_readonly` runs generated SQL: SELECT only, on the seven dataset tables, and the executor applies a 15 s query timeout.
   - `app_retrieval` is used by retrieval and can SELECT only from `document_embeddings`.
   - The owner connection (`DATABASE_URL`) is used for loading data, schema introspection and metrics, never for generated SQL.

Role definitions are in `infra/create_readonly_role.sql` and `infra/create_retrieval_role.sql`. Passwords are supplied at run time (psql variables) and are never committed. Keep credentials in `.env`, which is git-ignored.
## Requirements

- Python 3.12 or newer in a conda or venv environment (the pinned `numpy` needs 3.12+)
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

1. **Create `.env`** in the repo root with the variables in the Configuration table. `POSTGRES_DB` must be `sql_agent`, because the role scripts name that database. Fill in the two role URLs in step 8.
2. **Add the data.** The repository neither ships nor downloads the thelook CSV files. Put these seven files in `data/raw/thelook/`: `distribution_centers.csv`, `events.csv`, `inventory_items.csv`, `order_items.csv`, `orders.csv`, `products.csv`, `users.csv`.
3. *(Optional)* **Check the CSVs:** `python data/loaders/verify_schema.py` tests that the key columns are unique and non-null before anything is loaded.
4. **Load the tables:** `python data/loaders/load_data.py` loads every CSV in that folder into a table named after the file.
5. **Create indexes:** apply `infra/create_indexes.sql` (indexes on `events.session_id` and `events.event_type`).
6. **Create the retrieval table:** apply `infra/create_retrieval_table.sql`. It enables pgvector and (re)creates `document_embeddings`; it drops the table first, so running it again deletes stored embeddings.
   Also apply `infra/create_metrics_table.sql` (creates `agent_request_metrics`; without it, metrics are not recorded).
7. **Build embeddings:** `python data/loaders/load_embeddings.py` chunks `data_dictionary.md` and `business_glossary.md`, embeds them with Ollama (the embedding model must be pulled and Ollama running) and stores them in `document_embeddings`.
8. **Create the roles** (after the tables exist, because they `GRANT` on them). Each script takes its password as a psql variable and should be run as the admin user:
   ```
   psql -v ON_ERROR_STOP=1 -v ro_password='CHOOSE-A-PASSWORD' -f infra/create_readonly_role.sql
   psql -v ON_ERROR_STOP=1 -v retr_password='CHOOSE-A-PASSWORD' -f infra/create_retrieval_role.sql
   ```
   Then set `READONLY_DATABASE_URL` and `RETRIEVAL_DATABASE_URL` in `.env` to connect as `app_readonly` and `app_retrieval` with those passwords.

The SQL steps (5, 6, 8 and the metrics table) are SQL files. Run them with `psql` against the database in `DATABASE_URL` as the admin user, or, if you have no local `psql`, pipe the file into the container (PowerShell):

```
Get-Content infra\create_indexes.sql | docker compose -f infra/docker-compose.yml exec -T postgres psql -U <POSTGRES_USER> -d sql_agent
```

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

## Deployment

See [DEPLOY.md](DEPLOY.md) for a free Render + Neon + Groq setup (`render.yaml` included).

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
| `LLM_BASE_URL`, `LLM_API_KEY` | Hosted OpenAI-compatible chat API (`LLM_PROVIDER=openai_compatible`). |
| `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_DIMENSIONS` | Hosted embeddings (`EMBEDDING_PROVIDER=openai_compatible`); dimensions must match `vector(1024)`. |
| `CORS_ORIGINS`, `RATE_LIMIT_PER_MINUTE`, `DAILY_REQUEST_CAP` | Public-API settings: allowed origins, per-client and global request limits. |
| `VITE_API_URL` | Frontend build setting: API base URL (default `http://127.0.0.1:8000`). |
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
python -m pytest -q                    # unit tests (no database or model needed)
python eval/run_golden_eval.py         # 10 questions: easy, medium, hard, safety
python eval/run_red_team.py            # 32 requests: destructive, disguised and safe near-misses (intent check only)
python eval/run_db_role_check.py       # tries writes, file reads and a long sleep as the read-only role; all must be refused
python eval/run_repeated_eval.py --trials 5   # pass rate and p50/p90 latency over repeated runs
```

The unit tests need no database or Ollama: `conftest.py` loads `.env` if present and otherwise supplies placeholder `DATABASE_URL` and `READONLY_DATABASE_URL` values.

The golden eval checks answers against ground truth computed from the database. On the author's machine (Intel Arc iGPU, Vulkan, qwen3:8b) the current `main` scores 10/10 on the golden eval and 12/12 on the original red-team set. The red-team set has since grown to 32 requests (intent check only); the extended safety prompt passes all 32. A first run of the 28-case version missed 2 (a table-copy request and a grant-admin request); the prompt was then extended, and the 4 `v3_` cases written afterwards (2 destructive, 2 safe near-misses) all passed. Those 4 are the only unseen cases, so treat 32/32 as a development score. The SQL filter and the read-only database role would still have stopped both misses. Typical latency: plain COUNT(*) questions that take the shortcut about 3-8 s; other questions about 11-23 s, mostly spent processing the 1.5-2k-token generator and critic prompts on the iGPU. Questions that need a retry take 25-30 s. A retry costs roughly 10-20 s more. A repeated run (5 trials of all 10 questions, `eval/run_repeated_eval.py`) passed 50/50 with answered-question latency p50 13.2 s and p90 23.2 s; one question (`medium_03`) needed a retry in 3 of 5 trials.

## Ablation: do glossary retrieval and the critic help?

`eval/run_ablation.py` answers that on 42 held-out questions (joins, date boundaries, glossary definitions, empty results, harder aggregations) that are not in the golden or red-team sets. Each answer is compared with the rows of a hand-written reference query run on the same database, never with a model's opinion. The hardcoded shortcuts are switched off, so every number comes from the model.

| Config | What runs |
|---|---|
| A | SQL generation only (no retrieval, no critic, no retries) |
| B | A + glossary retrieval |
| C | B + critic and up to 2 retries (the full pipeline) |
| D | optional: critic and retries without retrieval |

It reports first-attempt and final correctness (with a 95% interval), questions fixed or broken by retries, wrong answers that were shown anyway, how often the critic accepted wrong SQL or rejected correct SQL, latency, tokens, and the full SQL traces of every fixed, broken or still-wrong question (`eval/results/ablation/REPORT.md`).

```
python eval/run_ablation.py --validate-reference   # run the 42 reference queries only
python eval/run_ablation.py --limit 5              # small trial
python eval/run_ablation.py                        # A, B and C on all questions
python eval/run_ablation.py --report-only          # rebuild the report
```

**Comparison rules.** Column names and order are ignored (extra columns allowed). Row order is ignored unless the question is a top-N question, and duplicate rows must match in number. Numbers match within a small tolerance (a percentage never matches a ratio), dates compare as text, and NULL matches only NULL. Empty-result questions should be checked by hand with `--validate-reference`, because two different queries can both return nothing on one snapshot for different reasons. Ties are avoided in the question set rather than handled in the comparator.

**Keep it a fair test.** Freeze the questions, reference queries, database snapshot, prompts and model before the comparison; the report prints a fingerprint of the question set. If you tune the agent against these questions afterwards, treat them as a development set and write a fresh final set. With 42 questions each one is about 2.4 percentage points, so read the counts and intervals, and repeat the run where you can.

Runs resume (`records.jsonl`), and a question that crashed, for example on a rate limit, is retried on the next run. Use `--pause 3` (or `EVAL_PAUSE_SECONDS`) to stay under provider limits. Free hosted tiers have daily token caps, so run it against local Ollama, or split it with `--categories`. Results are only meaningful if you publish the numbers you actually get, including a config where retries do not help.

### Results (local `qwen3:8b`, 42 questions, one run on 2026-10-28)

| Setup | Correct (of 42) | Wrong answers returned | No answer | Median time | Tokens / question |
|---|---|---|---|---|---|
| A. SQL generation only | 19 (45%) | 22 | 1 | 51 s | 1,900 |
| B. + glossary retrieval | 20 (48%) | 18 | 4 | 71 s | 2,200 |
| C. + critic and up to 2 retries | 24 (57%) | 15 | 3 | 85 s | 4,900 |

95% intervals for the final accuracy are roughly 31-60%, 33-62% and 42-71%, so they overlap: the gain from C is suggestive, not proven. Full report and every trace: `eval/results/ablation/REPORT.md` (question-set fingerprint `2bf45cd73ab2`).

What the experiment shows:

- **Retries helped a little and never hurt.** 12 questions were retried; 4 were fixed (`biz_06`, `empty_04`, `empty_05`, `agg_06`) and none went from right to wrong. The price was about 2.5x the tokens and roughly 35 s more per question.
- **The critic is cautious but blind to meaning.** Judged against the reference queries it made no false alarms (0 correct answers rejected) and all 9 rejections were right, but it accepted 15 wrong answers out of 39 it approved. Every wrong answer returned by setup C was one the critic had approved. A small model can catch a missing JOIN or a nonexistent column; it cannot check, for example, that `<= '2022-01-31'` drops most of the last day, or that a one-day question was answered with a one-month range (`date_03`).
- **Retrieval is not a clear win.** It helped the business-definition questions (3 to 5 of 10) but made the model add `status = 'Complete'` to questions that never asked for it (`join_04`, `join_06`, `join_07`, `join_08`, `date_04`, `date_09`).
- **Joins are the weak spot**: 1 of 8 in the full pipeline. The glossary explains definitions, not how tables connect; the model reached for denormalised columns on `inventory_items` or used `events` as a stand-in for orders.
- **Retries can repeat themselves.** In `join_03` the same SQL (a column that does not exist) was regenerated three times despite the database error being fed back.

Caveats: one run, one local 8B model, 42 questions, and the questions were seen while writing this section, so they are now a development set. Latency in the later part of setup C was inflated by laptop throttling (so compare the medians, not the p95). A hosted model may behave differently.

### Held-out check (30 new questions, same model, run on 2026-10-28)

The 30 questions in `eval/heldout_questions.py` and their reference results were committed before the agent was run on them, and no prompt or code was changed in between.

| Setup | Correct (of 30) | 95% range | Wrong answers returned | No answer |
|---|---|---|---|---|
| SQL only | 13 (43%) | 27-61% | 15 | 2 |
| + Retrieval | 17 (57%) | 39-73% | 11 | 2 |
| + Critic and retries | 20 (67%) | 49-81% | 6 | 4 |

The ordering matches the 42-question run, but with 30 questions the ranges overlap, so the size of each step is not established. Two results are negative. The critic marked every answer it reviewed as valid, including all 6 wrong answers the full pipeline returned, so it rejected nothing here. Retries ran on 4 questions, each time sent the same SQL again, and fixed none of them. The full pipeline's lead over retrieval alone came from questions where its first attempt happened to differ, not from the critic or retries. Disclosure: three of the 30 (`h_agg_01`, `h_agg_06`, `h_biz_01`) turned out to repeat questions from the 42-question development set, which I only found while preparing the next set. The agent was not tuned on either set, but those three are not independent. Without them the totals are 13/27 (48%), 16/27 (59%) and 19/27 (70%), and the conclusions above do not change. These 30 questions are now diagnostic: fixes made after reading these failures must be tested on a new set.

### Second held-out set (30 new questions), before and after two fixes

`eval/heldout2_questions.py` was frozen in git before the agent ran on it, with no overlap with the other sets (a test enforces this). It was run once on the code as it was, then twice after two changes designed from the first held-out set's failures: live value hints in the schema context (exact stored values of small text columns, such as `'Complete'` and `'F'`) and a retry guard (a retry may not resend the failed SQL, and errors get specific hints).

| Setup | Before fixes | After fixes, run 1 | After fixes, run 2 |
|---|---|---|---|
| SQL only | 16/30 (53%) | 23/30 (77%) | 23/30 (77%) |
| + Retrieval | 21/30 (70%) | 17/30 (57%) | 17/30 (57%) |
| + Critic and retries | 19/30 (63%) | 17/30 (57%) | 19/30 (63%) |

What this shows, and what it does not:
- The value hints fixed the wrong-spelling errors (`'female'`, `'completed'`) and lifted SQL-only accuracy by 7 questions.
- With the hints in place, adding the glossary retrieval made 6 questions worse and none better. The traces show the model adding an unrequested `status = 'Complete'` filter. This was noticed after seeing the v2 results, so treat it as a lead to confirm on a fresh set, not as a result.
- The critic still accepted most wrong answers. Retries fixed one question in the second run and broke one in the first.
- The two repeat runs gave almost the same answers, so the model is close to deterministic. Repeating therefore confirms reproducibility, not that the effect holds on other questions; with 30 questions the 95% ranges are about 20 points wide.
- The hints only cover text columns with 20 or fewer distinct values, so a country stored as `Brasil` is not covered.
- These 30 questions are now diagnostic. The deployed demo still uses retrieval plus the critic.

### Third held-out set (30 new questions), run after the fixes

`eval/heldout3_questions.py` was frozen in git before the run, and no code or prompt changed between freezing it and running it. Its purpose was to test the lead from the second set: with the value hints on, does adding glossary retrieval lower accuracy?

| Setup | Correct (of 30) | 95% range | Wrong answers returned | No answer |
|---|---|---|---|---|
| SQL only | 18 (60%) | 42-75% | 11 | 1 |
| + Retrieval | 15 (50%) | 33-67% | 12 | 3 |
| + Critic and retries | 16 (53%) | 36-70% | 14 | 0 |

- The direction repeated: SQL only was ahead of retrieval again. On this set alone it is not established: 6 questions were better without retrieval and 3 were better with it, which could be chance. Pooled with the second set the split is 12 to 3, but that set is where the idea came from, so treat the pooled figure as suggestive.
- Retries recovered 2 of the 6 retried questions and broke none. Both recoveries began with a database error (a missing column, a query that timed out). The four retries that followed a critic rejection stayed wrong.
- The critic approved most wrong answers again.
- The deployed demo has not been changed and still uses retrieval plus the critic.

## Limitations

Please read these before trusting the numbers above.

- **Small, partly tuned evaluation.** The golden set has 10 questions and the red-team set has 32 (12 original, 16 added in v2, 4 in v3). Some prompt sections and shortcuts were written while debugging these same questions, so the scores overstate general accuracy.
- **Hardcoded shortcuts.** `deterministic_sql` shortcuts and exact-SQL acceptance rules in `critic_node.py` (for a plain distinct-session count and the conversion-rate query) would accept those exact queries without asking the model. In the recorded runs they did not trigger, because the generator's SQL carries column aliases and so does not match, and the LLM critic judged those questions. The two opt-in critic shortcuts above are narrower and tested, but they are still special cases.
- **An 8B critic is unreliable.** It sometimes rejects correct SQL (for example, `COUNT(DISTINCT session_id) ... WHERE event_type = 'purchase'` for "sessions that contain a purchase event"). Prompt wording did not fix this; the code shortcut does for that shape only.
- **Generator first attempts vary.** For some questions the first SQL is wrong and is fixed on retry, which is the main source of slow answers.
- **Single dataset, single statement.** Only one dataset is configured, and only one SELECT is allowed per request.
- **Development defaults.** The Docker Compose file publishes Postgres on 127.0.0.1 only, but still passes the whole `.env` to the database container. Do not expose it beyond a development machine as-is.
- **Metrics use the owner connection** rather than a dedicated metrics role.
- **No load testing.** The hosted demo is a deployed prototype with a deliberate request cap; concurrency and sustained-load behaviour have not been measured.