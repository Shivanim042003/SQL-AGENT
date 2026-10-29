"""Static SQL safety check (no database or model needed)."""

import pytest

from app.agent.sql_safety import check_sql_safety, clean_sql
from eval.ablation_questions import QUESTIONS

BLOCKED = [
    # (label, sql)
    ("plain delete", "DELETE FROM events"),
    ("cte delete", "WITH x AS (DELETE FROM events RETURNING 1) SELECT 1"),
    ("cte delete newline", "WITH x AS (DELETE\nFROM events RETURNING 1) SELECT 1"),
    ("cte delete tab", "WITH x AS (DELETE\tFROM events RETURNING 1) SELECT 1"),
    ("cte delete comment", "WITH x AS (DELETE/**/FROM events RETURNING 1) SELECT 1"),
    ("cte update", "WITH x AS (UPDATE users SET age = 1 RETURNING 1) SELECT 1"),
    ("cte insert", "WITH x AS (INSERT INTO users DEFAULT VALUES RETURNING 1) SELECT 1"),
    ("mixed case", "WiTh x AS (DeLeTe FROM events RETURNING 1) SELECT 1"),
    ("select into", "SELECT * INTO newtab FROM events"),
    ("two statements", "SELECT 1; SELECT 2"),
    ("trailing drop", "SELECT 1; DROP TABLE events"),
    ("sleep", "SELECT pg_sleep(100)"),
    ("sleep mixed case", "SELECT Pg_Sleep(100)"),
    ("read file", "SELECT pg_read_file('/etc/passwd')"),
    ("list dir", "SELECT pg_ls_dir('/')"),
    ("set config", "SELECT set_config('statement_timeout', '0', false)"),
    ("dblink", "SELECT * FROM dblink('host=x', 'select 1') AS t(a int)"),
    ("sequence", "SELECT nextval('users_id_seq')"),
    ("copy", "COPY events TO PROGRAM 'curl x'"),
    ("create", "CREATE TABLE t AS SELECT 1"),
    ("not select", "EXPLAIN ANALYZE DELETE FROM events"),
    ("empty", ""),
]

ALLOWED = [
    "SELECT COUNT(*) FROM events",
    "select count(*) from orders where created_at >= '2022-01-01'",
    "WITH s AS (SELECT session_id FROM events) SELECT COUNT(*) FROM s",
    "SELECT created_at, updated_at FROM users",          # similar-looking names
    "SELECT * FROM users WHERE first_name = 'update'",    # keyword inside text
    "SELECT * FROM users WHERE first_name = 'x; DROP'",   # ; inside text
    "SELECT 1 -- delete everything",                      # keyword in comment
    "SELECT /* drop table */ 1",
    'SELECT "update" FROM t',                             # quoted identifier
    "(SELECT 1) UNION (SELECT 2)",
    "SELECT EXTRACT(EPOCH FROM (shipped_at - created_at)) FROM orders",
]


@pytest.mark.parametrize("label,sql", BLOCKED)
def test_blocked(label, sql):
    assert check_sql_safety(sql) is not None, label


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed(sql):
    assert check_sql_safety(sql) is None, sql


def test_all_reference_queries_pass():
    for q in QUESTIONS:
        assert check_sql_safety(q["reference_sql"]) is None, q["id"]


def test_clean_sql_hides_literals_and_comments():
    cleaned = clean_sql("SELECT 'DELETE' /* drop */ -- insert\n FROM t")
    assert "delete" not in cleaned and "drop" not in cleaned
    assert "insert" not in cleaned


def test_generator_rejects_whitespace_disguised_delete(monkeypatch):
    """End to end through generate_sql with a stub model."""

    import json

    import app.agent.sql_generator as gen
    import config

    monkeypatch.setattr(config, "DISABLE_SHORTCUTS", True)

    class Client:
        def complete(self, *args, **kwargs):
            class Response:
                content = json.dumps({
                    "sql": "WITH x AS (DELETE\nFROM events RETURNING 1) SELECT 1"
                })

            return Response()

    monkeypatch.setattr(gen, "get_llm_client", lambda *a, **k: Client())
    out = gen.generate_sql({
        "question": "an unrelated test question",
        "schema": "", "retrieved_context": "", "retry_count": 0,
    })

    assert out["sql"] == ""
    assert "prohibited keyword: delete" in out["error"]
    assert out["error_type"] == "SQL_GENERATION_ERROR"
