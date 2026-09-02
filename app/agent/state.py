from typing import TypedDict


class AgentState(TypedDict):
    """Shared state passed between agent workflow steps."""

    question: str

    schema: str

    retrieved_context: str

    sql: str | None

    query_result: list | None

    error: str | None

    final_answer: str | None