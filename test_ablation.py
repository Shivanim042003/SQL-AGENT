"""Tests for the ablation evaluation helpers and graph switches (no DB/LLM)."""

import datetime
from decimal import Decimal

import pytest

import eval.run_ablation as ra
from app.agent import graph as graph_module
from eval.ablation_lib import (
    build_report,
    critic_confusion,
    outcome,
    results_match,
    summarize,
    wilson_interval,
)
from eval.ablation_questions import QUESTIONS


# ---------------- comparator ----------------

def test_scalar_match_ignores_name_and_type():
    assert results_match([[5]], [{"anything": Decimal("5")}])


def test_scalar_mismatch():
    assert not results_match([[5]], [{"c": 6}])


def test_float_tolerance():
    assert results_match([[12.3456]], [{"x": Decimal("12.35")}])
    assert not results_match([[12.3456]], [{"x": 13.0}])


def test_percentage_is_not_a_ratio():
    assert not results_match([[41.2]], [{"rate": 0.412}])


def test_row_order_ignored_unless_ordered():
    ref = [["a", 2], ["b", 1]]
    act = [{"k": "b", "n": 1}, {"k": "a", "n": 2}]
    assert results_match(ref, act)
    assert not results_match(ref, act, ordered=True)


def test_extra_columns_allowed_and_column_order_free():
    ref = [["CA", 10]]
    assert results_match(ref, [{"n": 10, "state": "CA"}])
    assert results_match(ref, [{"id": 7, "state": "CA", "n": 10}])
    assert not results_match(
        ref, [{"id": 7, "state": "CA", "n": 10}], allow_extra_columns=False
    )


def test_extra_columns_do_not_hide_wrong_values():
    assert not results_match([["CA", 10]], [{"s": "CA", "n": 11, "x": 1}])


def test_empty_results():
    assert results_match([], [])
    assert not results_match([], [{"id": 1}])
    assert not results_match([[1]], [])


def test_null_value():
    assert results_match([[None]], [{"avg": None}])
    assert not results_match([[None]], [{"avg": 0}])


def test_dates_compare_as_text():
    d = datetime.date(2022, 1, 1)
    assert results_match([[d]], [{"d": d}])


def test_row_count_must_match():
    assert not results_match([[1], [2]], [{"a": 1}])


# ---------------- summary and report ----------------

def rec(first, final, answered=True, latency=1.0, tokens=100, retries=0, cat="x"):
    return {
        "id": f"q{first}{final}{retries}", "category": cat, "question": "q",
        "first_correct": first, "final_correct": final, "answered": answered,
        "latency": latency, "tokens": tokens, "retries": retries,
        "attempts": [],
    }


def test_summarize_counts_corrections_and_harm():
    records = [
        rec(True, True),
        rec(False, True, retries=1),
        rec(True, False, retries=1),
        rec(False, False, answered=False),
    ]
    s = summarize(records)
    assert s["successful_corrections"] == 1
    assert s["harmful_corrections"] == 1
    assert s["first_attempt_correct"] == 2
    assert s["final_correct"] == 2
    assert s["confident_wrong"] == 1  # answered and wrong
    assert s["total_retries"] == 2


def test_outcome_labels():
    assert outcome(rec(True, True)) == "right_both"
    assert outcome(rec(False, True)) == "fixed"
    assert outcome(rec(True, False)) == "broken"
    assert outcome(rec(False, False)) == "wrong_both"


def test_wilson_interval_bounds():
    low, high = wilson_interval(30, 40)
    assert 0.5 < low < 0.75 < high < 0.9
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_critic_confusion():
    r = rec(True, True)
    r["attempts"] = [
        {"error": None, "critic_valid": True, "correct": True},
        {"error": None, "critic_valid": True, "correct": False},
        {"error": None, "critic_valid": False, "correct": True},
        {"error": None, "critic_valid": False, "correct": False},
        {"error": "boom", "critic_valid": False, "correct": False},
        {"error": None, "critic_valid": None, "correct": True},
    ]
    assert critic_confusion([r]) == {
        "accepted_correct": 1, "accepted_wrong": 1,
        "rejected_correct": 1, "rejected_wrong": 1,
    }


def test_report_renders():
    r = rec(False, True, retries=1, cat="joins")
    r["id"] = "join_01"
    r["attempts"] = [
        {"sql": "SELECT 1", "rows": [{"a": 1}], "error": None,
         "correct": False, "critic_valid": False, "critique": "wrong"},
        {"sql": "SELECT 2", "rows": [{"a": 2}], "error": None,
         "correct": True, "critic_valid": True, "critique": ""},
    ]
    text = build_report(
        {"A": [rec(True, True, cat="joins")], "C": [r]}, ["A", "C"],
        {"join_01": {"category": "joins", "reference_sql": "SELECT 2"}},
    )
    assert "Fixed by retry" in text
    assert "join_01" in text and "SELECT 2" in text


# ---------------- question set ----------------

def test_questions_are_well_formed():
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))
    for q in QUESTIONS:
        assert q["question"].strip() and q["reference_sql"].strip()
        assert q["reference_sql"].lstrip().lower().startswith(("select", "with"))


def test_questions_do_not_overlap_golden_or_shortcuts(monkeypatch):
    import config
    from app.agent.sql_generator import deterministic_sql

    monkeypatch.setattr(config, "DISABLE_SHORTCUTS", False)
    from eval.golden_questions import GOLDEN_QUESTIONS

    golden = {g["question"].lower() for g in GOLDEN_QUESTIONS}
    for q in QUESTIONS:
        assert q["question"].lower() not in golden
        assert deterministic_sql(q["question"]) is None


# ---------------- graph switches ----------------

def _patched_graph(monkeypatch, sqls, critic_verdicts=None):
    """Graph with stubbed LLM/DB nodes. Returns (graph, calls)."""

    calls = {"gen": 0, "critic": 0, "retrieval": 0}
    verdicts = list(critic_verdicts or [])

    monkeypatch.setattr(
        graph_module, "check_intent", lambda s: {"is_destructive": False}
    )
    monkeypatch.setattr(graph_module, "load_schema", lambda s: {"schema": "s"})

    def retrieve(s):
        calls["retrieval"] += 1
        return {"retrieved_context": "ctx"}

    def generate(s):
        sql = sqls[min(calls["gen"], len(sqls) - 1)]
        calls["gen"] += 1
        return {"sql": sql, "error": None, "error_type": "NONE"}

    def execute(s):
        return {"query_result": [{"v": s["sql"]}], "error": None,
                "error_type": "NONE"}

    def critic(s):
        calls["critic"] += 1
        ok = verdicts.pop(0) if verdicts else True
        return {"sql_valid": ok, "critique": "" if ok else "bad",
                "error_type": "NONE"}

    monkeypatch.setattr(graph_module, "retrieve_context", retrieve)
    monkeypatch.setattr(graph_module, "generate_sql", generate)
    monkeypatch.setattr(graph_module, "execute_sql", execute)
    monkeypatch.setattr(graph_module, "critique_with_fast_path", critic)

    return graph_module, calls


def _run(graph):
    return graph.invoke(ra.initial_state("q"))


def test_default_graph_retries_until_critic_accepts(monkeypatch):
    gm, calls = _patched_graph(monkeypatch, ["bad", "good"], [False, True])
    final = _run(gm.build_graph())
    assert calls == {"gen": 2, "critic": 2, "retrieval": 1}
    assert final["query_result"] == [{"v": "good"}]


def test_no_critic_no_retries_accepts_first_sql(monkeypatch):
    gm, calls = _patched_graph(monkeypatch, ["bad", "good"], [False, True])
    final = _run(gm.build_graph(
        use_retrieval=False, use_critic=False, max_retries=0
    ))
    assert calls == {"gen": 1, "critic": 0, "retrieval": 0}
    assert final["sql_valid"] is True
    assert final["query_result"] == [{"v": "bad"}]


def test_retry_limit_is_configurable(monkeypatch):
    gm, calls = _patched_graph(monkeypatch, ["a"], [False] * 10)
    final = _run(gm.build_graph(max_retries=1))
    assert calls["gen"] == 2
    assert not final["sql_valid"]


def test_skip_critic_rejects_execution_errors():
    out = graph_module.skip_critic({"error": "boom"})
    assert out["sql_valid"] is False
    assert graph_module.skip_critic({"error": None})["sql_valid"] is True


# ---------------- run_question with a stub graph ----------------

class FakeGraph:
    def __init__(self, chunks):
        self.chunks = chunks

    def stream(self, state, stream_mode):
        assert stream_mode == "updates"
        yield from self.chunks


def test_run_question_scores_attempts_against_reference():
    q = {"id": "t1", "category": "x", "question": "q"}
    chunks = [
        {"generate_sql": {"sql": "SELECT 1"}},
        {"execute_sql": {"query_result": [{"n": 1}], "error": None}},
        {"critique_sql": {"sql_valid": False, "critique": "no"}},
        {"prepare_retry": {"sql": None, "query_result": None}},
        {"generate_sql": {"sql": "SELECT 2"}},
        {"execute_sql": {"query_result": [{"n": 2}], "error": None}},
        {"critique_sql": {"sql_valid": True, "critique": ""}},
        {"format_answer": {"final_answer": "Result: 2"}},
    ]
    record = ra.run_question(FakeGraph(chunks), q, [[2]])
    assert record["first_correct"] is False
    assert record["final_correct"] is True
    assert record["retries"] == 1
    assert record["attempts"][0]["critic_valid"] is False
    assert outcome(record) == "fixed"


def test_run_question_unanswered_is_not_correct():
    q = {"id": "t2", "category": "x", "question": "q"}
    chunks = [
        {"generate_sql": {"sql": "SELECT 1"}},
        {"execute_sql": {"query_result": [{"n": 1}], "error": None}},
        {"critique_sql": {"sql_valid": False, "critique": "no"}},
        {"format_answer": {"final_answer": "I wasn't able"}},
    ]
    record = ra.run_question(FakeGraph(chunks), q, [[1]])
    assert record["first_correct"] is True
    assert record["final_correct"] is False  # never shown to the user
    assert outcome(record) == "broken"


def test_run_question_records_crash():
    class Boom:
        def stream(self, state, stream_mode):
            raise RuntimeError("429")
            yield  # pragma: no cover

    record = ra.run_question(
        Boom(), {"id": "t3", "category": "x", "question": "q"}, [[1]]
    )
    assert "429" in record["crashed"]
    assert record["final_correct"] is False


def test_run_question_with_real_langgraph_stream(monkeypatch):
    """The real graph's update stream has the shape run_question expects."""

    gm, _ = _patched_graph(monkeypatch, ["bad", "good"], [False, True])
    q = {"id": "t4", "category": "x", "question": "q"}
    record = ra.run_question(gm.build_graph(), q, [["good"]])

    assert record["crashed"] is None
    assert [a["sql"] for a in record["attempts"]] == ["bad", "good"]
    assert record["first_correct"] is False
    assert record["final_correct"] is True
    assert record["answered"] is True


def test_shortcut_switch_disables_hardcoded_sql(monkeypatch):
    import config
    from app.agent.sql_generator import deterministic_sql

    question = "How many events are in the database?"
    monkeypatch.setattr(config, "DISABLE_SHORTCUTS", False)
    assert deterministic_sql(question) is not None
    monkeypatch.setattr(config, "DISABLE_SHORTCUTS", True)
    assert deterministic_sql(question) is None


def test_shortcut_switch_sends_known_question_to_llm_critic(monkeypatch):
    import config
    from app.agent import critic_node

    class Client:
        calls = 0

        def complete(self, system, messages, **kwargs):
            Client.calls += 1

            class Response:
                content = '{"valid": false, "feedback": "judged by model"}'

            return Response()

    monkeypatch.setattr(critic_node, "get_llm_client", lambda *a, **k: Client())
    state = {
        "question": "How many events are in the database?",
        "sql": "SELECT COUNT(*) FROM events",
        "query_result": [{"count": 1}],
        "error": None,
        "retry_count": 0,
    }

    monkeypatch.setattr(config, "DISABLE_SHORTCUTS", False)
    assert critic_node.critique_sql(state)["sql_valid"] is True
    assert Client.calls == 0  # hardcoded rule accepted it

    monkeypatch.setattr(config, "DISABLE_SHORTCUTS", True)
    out = critic_node.critique_sql(state)
    assert Client.calls == 1  # the model judged it instead
    assert out["sql_valid"] is False


def test_critic_verdicts_ignored_when_config_has_no_critic():
    q = {"id": "t5", "category": "x", "question": "q"}
    chunks = [
        {"generate_sql": {"sql": "SELECT 1"}},
        {"execute_sql": {"query_result": [{"n": 1}], "error": None}},
        {"critique_sql": {"sql_valid": True, "critique": ""}},
        {"format_answer": {"final_answer": "Result"}},
    ]
    record = ra.run_question(FakeGraph(chunks), q, [[1]], has_critic=False)
    assert "critic_valid" not in record["attempts"][0]
    assert record["final_correct"] is True
