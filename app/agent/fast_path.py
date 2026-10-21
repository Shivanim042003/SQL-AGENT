"""
Optional shortcut that skips the LLM critic for trivially verifiable queries.

Off by default. Enable with SKIP_CRITIC_FOR_SIMPLE_COUNTS=1.

The critic is skipped only when ALL of these hold:
  * the question is exactly "How many <table words> are there?" (no filters)
  * the SQL is exactly SELECT COUNT(*) FROM <that table>
  * execution succeeded and returned a single integer
  * this is the first attempt (no retry)

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

    rows = state.get("query_result")
    if not isinstance(rows, list) or len(rows) != 1:
        return False

    row = rows[0]
    values = list(row.values()) if isinstance(row, dict) else list(row)
    return (
        len(values) == 1
        and isinstance(values[0], int)
        and not isinstance(values[0], bool)
    )


def critique_with_fast_path(state) -> dict:
    if config.SKIP_CRITIC_FOR_SIMPLE_COUNTS and is_simple_count(state):
        latencies = dict(state.get("latencies", {}))
        latencies["critic"] = 0.0
        return {
            "sql_valid": True,
            "critique": "Accepted without the LLM critic: plain COUNT(*) on the table the question names.",
            "error_type": ErrorType.NONE.value,
            "latencies": latencies,
            "retry_latencies": {
                key: dict(value)
                for key, value in state.get("retry_latencies", {}).items()
            },
        }

    return critique_sql(state)