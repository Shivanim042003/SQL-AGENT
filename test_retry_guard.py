import json

import config
from app.agent import sql_generator
from app.agent.retry_guard import build_retry_hints, is_repeat, tables_with_column
from app.core.error_types import ErrorType
from app.execution.value_hints import format_value_hints

SCHEMA = (
    "order_items: id (integer), status (text), sale_price (double precision)\n"
    "products: id (integer), brand (text), category (text)\n"
    "inventory_items: id (integer), product_brand (text)"
)


def test_is_repeat_ignores_case_spacing_and_semicolon():
    assert is_repeat("SELECT  1 ;", "select 1")
    assert not is_repeat("select 2", "select 1")
    assert not is_repeat("", "")


def test_missing_column_hint_names_the_right_table():
    err = 'SQL execution failed: column "product_brand" does not exist'
    assert tables_with_column("product_brand", SCHEMA) == ["inventory_items"]
    assert "inventory_items" in build_retry_hints(err, SCHEMA)


def test_unknown_column_hint_and_timeout_hint():
    assert "No table has" in build_retry_hints('column "zzz" does not exist', SCHEMA)
    assert "correlated" in build_retry_hints("canceling statement due to statement timeout", SCHEMA)
    assert build_retry_hints("some other error", SCHEMA) == ""


def test_value_hints_only_list_fully_covered_small_columns():
    rows = [
        ("orders", "status", ["Complete", "Cancelled"], 2),
        ("users", "gender", ["F", "M"], 2),
        ("users", "email", ["a@x.com"], 500),          # not fully listed: skipped
        ("document_embeddings", "source", ["x"], 1),   # excluded table
        ("events", "uri", None, 3),                    # no stats: skipped
    ]
    text = format_value_hints(rows)
    assert "orders.status: 'Cancelled', 'Complete'" in text
    assert "users.gender: 'F', 'M'" in text
    assert "email" not in text and "document_embeddings" not in text and "uri" not in text
    assert format_value_hints([]) == ""


class FakeClient:
    def __init__(self, sqls):
        self.sqls = list(sqls)

    def complete(self, system, messages, max_tokens=256, think=False):
        class R:
            pass
        r = R()
        r.content = json.dumps({"sql": self.sqls.pop(0)})
        return r


def _state(previous):
    return {
        "question": "zzz unmatched question about nothing",
        "schema": SCHEMA,
        "retrieved_context": "",
        "previous_sql": previous,
        "critique": 'SQL execution failed: column "product_brand" does not exist',
        "retry_count": 1,
        "latencies": {},
        "retry_latencies": {},
    }


def test_guard_accepts_a_changed_second_attempt(monkeypatch):
    monkeypatch.setattr(config, "RETRY_GUARD", True)
    client = FakeClient(["SELECT 1 FROM a", "SELECT 2 FROM b"])
    monkeypatch.setattr(sql_generator, "get_llm_client", lambda: client)
    out = sql_generator.generate_sql(_state("SELECT 1 FROM a"))
    assert out["sql"] == "SELECT 2 FROM b"
    assert out["error_type"] == ErrorType.NONE.value


def test_guard_gives_up_when_model_repeats_twice(monkeypatch):
    monkeypatch.setattr(config, "RETRY_GUARD", True)
    client = FakeClient(["SELECT 1 FROM a", "select 1 from a;"])
    monkeypatch.setattr(sql_generator, "get_llm_client", lambda: client)
    out = sql_generator.generate_sql(_state("SELECT 1 FROM a"))
    assert out["sql"] == ""
    assert out["error_type"] == ErrorType.SQL_GENERATION_ERROR.value


def test_guard_off_keeps_old_behaviour(monkeypatch):
    monkeypatch.setattr(config, "RETRY_GUARD", False)
    client = FakeClient(["SELECT 1 FROM a"])
    monkeypatch.setattr(sql_generator, "get_llm_client", lambda: client)
    out = sql_generator.generate_sql(_state("SELECT 1 FROM a"))
    assert out["sql"] == "SELECT 1 FROM a"
