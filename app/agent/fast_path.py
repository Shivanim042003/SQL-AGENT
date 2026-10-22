"""
Optional shortcuts that skip the LLM critic for trivially verifiable queries.

Off by default. Enable with SKIP_CRITIC_FOR_SIMPLE_COUNTS=1.

Shortcut 1 (plain count). The critic is skipped only when ALL of these hold:
  * the question is exactly "How many <table words> are there?" (no filters)
  * the SQL is exactly SELECT COUNT(*) FROM <that table>
  * execution succeeded and returned a single integer
  * this is the first attempt (no retry)

Shortcut 2 (sessions containing an event type). The critic is skipped only when:
  * the question is exactly "How many sessions contain/have/include/with a <x> event?"
  * the SQL is exactly SELECT COUNT(DISTINCT session_id) FROM events
    WHERE event_type = '<x>' with the same <x> as the question
  * execution succeeded and returned a single integer greater than 0
  * there was no execution error (a retry attempt is fine: correctness depends
    only on the question/SQL match, not on which attempt produced it)

Anything else goes to the normal LLM critic.
"""

import re

import config
from app.agent.critic_node import critique_sql
from app.core.error_types import ErrorType

_SQL = re.compile(
    r"^\s*select\s+count\(\*\)(?:\s+as\s+\w+)?\s+from\s+(?P<table>[a-z_][a-z0-9_]*)\s*;?\s*$",
    re.IGNORECASE,
)

_QUESTION = re.compile(
    r"^\s*how\s+many\s+(?P<entity>[a-z_ ]+?)"
    r"(?:\s+(?:are\s+there(?:\s+in\s+the\s+database)?|are\s+in\s+the\s+database"
    r"|exist|do\s+we\s+have|in\s+total))?"
    r"\s*\??\s*$",
    re.IGNORECASE,
)

_SESSION_SQL = re.compile(
    r"^\s*select\s+count\(\s*distinct\s+session_id\s*\)(?:\s+as\s+\w+)?"
    r"\s+from\s+events\s+where\s+event_type\s*=\s*'(?P<etype>[a-z_]+)'\s*;?\s*$",
    re.IGNORECASE,
)

_SESSION_QUESTION = re.compile(
    r"^\s*how\s+many\s+sessions\s+(?:contain|contains|have|has|include|includes|with)"
    r"\s+(?:an?\s+|the\s+)?(?P<etype>[a-z_]+)\s+events?\s*\??\s*$",
    re.IGNORECASE,
)


def _single_int(rows):
    if not isinstance(rows, list) or len(rows) != 1:
        return None
    row = rows[0]
    values = list(row.values()) if isinstance(row, dict) else list(row)
    if (
        len(values) == 1
        and isinstance(values[0], int)
        and not isinstance(values[0], bool)
    ):
        return values[0]
    return None


def is_simple_count(state) -> bool:
    if state.get("error") or state.get("retry_count", 0) != 0:
        return False

    sql_match = _SQL.match(state.get("sql") or "")
    question_match = _QUESTION.match(state.get("question") or "")
    if not sql_match or not question_match:
        return False

    table = sql_match.group("table").lower().replace("_", " ")
    entity = " ".join(question_match.group("entity").lower().replace("_", " ").split())
    if table != entity:
        return False

    return _single_int(state.get("query_result")) is not None


def is_session_filter_count(state) -> bool:
    # Any attempt may be accepted: correctness depends only on the exact
    # question/SQL match, not on which attempt produced the SQL.
    if state.get("error"):
        return False

    sql_match = _SESSION_SQL.match(state.get("sql") or "")
    question_match = _SESSION_QUESTION.match(state.get("question") or "")
    if not sql_match or not question_match:
        return False

    # The SQL value must be the lowercase event type named in the question.
    if sql_match.group("etype") != question_match.group("etype").lower():
        return False

    count = _single_int(state.get("query_result"))
    return count is not None and count > 0


def _accept(state, reason: str) -> dict:
    latencies = dict(state.get("latencies", {}))
    latencies["critic"] = 0.0
    return {
        "sql_valid": True,
        "critique": reason,
        "error_type": ErrorType.NONE.value,
        "latencies": latencies,
        "retry_latencies": {
            key: dict(value)
            for key, value in state.get("retry_latencies", {}).items()
        },
    }


def critique_with_fast_path(state) -> dict:
    if config.SKIP_CRITIC_FOR_SIMPLE_COUNTS:
        if is_simple_count(state):
            return _accept(
                state,
                "Accepted without the LLM critic: plain COUNT(*) on the table the question names.",
            )
        if is_session_filter_count(state):
            return _accept(
                state,
                "Accepted without the LLM critic: COUNT(DISTINCT session_id) filtered by the event type the question names.",
            )

    return critique_sql(state)