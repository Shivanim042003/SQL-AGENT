from typing import TypedDict


class AgentState(TypedDict):
    """Shared state passed between all agent workflow steps."""

    request_id: str

    question: str
    is_destructive: bool
    schema: str
    retrieved_context: str

    sql: str | None
    previous_sql: str | None

    query_result: list | None

    error: str | None
    error_type: str

    sql_valid: bool
    critique: str

    retry_count: int

    final_answer: str | None