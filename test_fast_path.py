import pytest

import config
from app.agent import fast_path


def make_state(question="How many events are there?",
               sql="SELECT COUNT(*) AS event_count FROM events;",
               rows=None, **extra):
    state = {
        "question": question,
        "sql": sql,
        "query_result": [{"event_count": 123}] if rows is None else rows,
        "error": None,
        "error_type": "NONE",
        "retry_count": 0,
        "latencies": {},
        "retry_latencies": {},
    }
    state.update(extra)
    return state


def test_plain_count_is_accepted_without_critic(monkeypatch):
    monkeypatch.setattr(config, "SKIP_CRITIC_FOR_SIMPLE_COUNTS", True)

    def boom(state):
        raise AssertionError("the LLM critic should not run")

    monkeypatch.setattr(fast_path, "critique_sql", boom)

    result = fast_path.critique_with_fast_path(make_state())

    assert result["sql_valid"] is True
    assert result["error_type"] == "NONE"


@pytest.mark.parametrize("state", [
    make_state(question="How many purchase events are there?"),
    make_state(sql="SELECT COUNT(*) FROM events WHERE event_type = 'purchase';"),
    make_state(question="How many sessions are there?"),
    make_state(rows=[{"a": 1}, {"a": 2}]),
    make_state(retry_count=1),
    make_state(error="boom"),
])
def test_everything_else_goes_to_the_critic(monkeypatch, state):
    monkeypatch.setattr(config, "SKIP_CRITIC_FOR_SIMPLE_COUNTS", True)
    called = []
    monkeypatch.setattr(
        fast_path, "critique_sql", lambda s: called.append(1) or {"sql_valid": False}
    )

    fast_path.critique_with_fast_path(state)

    assert called


def test_flag_off_always_uses_the_critic(monkeypatch):
    monkeypatch.setattr(config, "SKIP_CRITIC_FOR_SIMPLE_COUNTS", False)
    called = []
    monkeypatch.setattr(
        fast_path, "critique_sql", lambda s: called.append(1) or {"sql_valid": True}
    )

    fast_path.critique_with_fast_path(make_state())

    assert called