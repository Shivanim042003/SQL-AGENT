from typing import TypedDict


class AgentState(TypedDict):
    """Shared state passed between all agent workflow steps."""

    # User input
    question: str

    # Safety
    is_destructive: bool

    # Database grounding
    schema: str
    retrieved_context: str

    # SQL generation
    sql: str | None
    previous_sql: str | None

    # SQL execution
    query_result: list | None
    error: str | None

    # Critic
    sql_valid: bool
    critique: str

    # Retry control
    retry_count: int

    # Final response
    final_answer: str | None