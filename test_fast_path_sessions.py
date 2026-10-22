import pytest

import config
from app.agent import fast_path
from app.agent.fast_path import critique_with_fast_path, is_session_filter_count

GOOD_SQL = "SELECT COUNT(DISTINCT session_id) AS sessions_with_purchase FROM events WHERE event_type = 'purchase';"


def make_state(**overrides):
    state = {
        "question": "How many sessions contain a purchase event?",
        "sql": GOOD_SQL,
        "query_result": [{"sessions_with_purchase": 181759}],
        "retry_count": 0,
        "error": None,
        "latencies": {},
        "retry_latencies": {},
    }
    state.update(overrides)
    return state


@pytest.mark.parametrize(
    "question,sql",
    [
        ("How many sessions contain a purchase event?", GOOD_SQL),
        ("how many sessions have a cart event", "select count(distinct session_id) from events where event_type = 'cart'"),
        ("How many sessions include purchase events?", "SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type='purchase'"),
        ("How many sessions with a home event?", "SELECT COUNT(DISTINCT session_id) AS n FROM events WHERE event_type = 'home'"),
    ],
)
def test_accepts_matching_session_count(question, sql):
    assert is_session_filter_count(make_state(question=question, sql=sql))


@pytest.mark.parametrize(
    "overrides",
    [
        {"question": "How many sessions contain a cart event?"},
        {"question": "How many sessions do not contain a purchase event?"},
        {"question": "How many sessions are there without a purchase event?"},
        {"question": "How many sessions contain a purchase event and a cart event?"},
        {"sql": "SELECT COUNT(DISTINCT session_id) FROM events"},
        {"sql": GOOD_SQL.rstrip(";") + " AND user_id = 1"},
        {"sql": "SELECT COUNT(*) FROM events WHERE event_type = 'purchase'"},
        {"sql": GOOD_SQL.replace("'purchase'", "'Purchase'")},
        {"query_result": [{"n": 0}]},
        {"query_result": [{"n": 1}, {"n": 2}]},
        {"query_result": [{"n": "5"}]},
        {"error": "boom"},
    ],
)
def test_rejects_everything_else(overrides):
    assert not is_session_filter_count(make_state(**overrides))


def test_flag_off_uses_llm_critic(monkeypatch):
    monkeypatch.setattr(config, "SKIP_CRITIC_FOR_SIMPLE_COUNTS", False)
    monkeypatch.setattr(fast_path, "critique_sql", lambda state: {"sentinel": True})
    assert critique_with_fast_path(make_state()) == {"sentinel": True}


def test_flag_on_skips_llm_critic(monkeypatch):
    monkeypatch.setattr(config, "SKIP_CRITIC_FOR_SIMPLE_COUNTS", True)

    def boom(state):
        raise AssertionError("critic should not be called")

    monkeypatch.setattr(fast_path, "critique_sql", boom)
    result = critique_with_fast_path(make_state())
    assert result["sql_valid"] is True
    assert result["error_type"] == "NONE"
    assert result["latencies"]["critic"] == 0.0


def test_flag_on_still_calls_critic_for_other_queries(monkeypatch):
    monkeypatch.setattr(config, "SKIP_CRITIC_FOR_SIMPLE_COUNTS", True)
    monkeypatch.setattr(fast_path, "critique_sql", lambda state: {"sentinel": True})
    state = make_state(sql=GOOD_SQL.rstrip(";") + " AND user_id = 1")
    assert critique_with_fast_path(state) == {"sentinel": True}

def test_accepts_on_retry_attempt():
    assert is_session_filter_count(make_state(retry_count=1))
