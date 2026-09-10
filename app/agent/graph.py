from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState

from app.agent.intent_node import check_intent
from app.agent.schema_node import load_schema
from app.agent.retrieval_node import retrieve_context
from app.agent.sql_generator import generate_sql
from app.agent.executor_node import execute_sql
from app.agent.critic_node import critique_sql
from app.agent.answer_node import format_answer

from app.core.error_types import ErrorType


# ============================================================
# CONFIGURATION
# ============================================================

MAX_RETRIES = 2


# ============================================================
# ROUTE AFTER INTENT
# ============================================================

def route_after_intent(state: AgentState):
    """
    Decide whether the request can continue into the
    database pipeline.
    """

    error_type = state.get(
        "error_type",
        ErrorType.NONE.value
    )

    # --------------------------------------------------------
    # SAFETY BLOCK
    # --------------------------------------------------------

    if error_type == ErrorType.SAFETY_BLOCK.value:
        return "format_answer"

    # --------------------------------------------------------
    # SAFETY-CHECK FAILURE
    # --------------------------------------------------------
    #
    # If the safety check itself failed, do not continue.
    # We cannot safely determine whether the request is safe.
    # --------------------------------------------------------

    if error_type == ErrorType.LLM_ERROR.value:
        return "format_answer"

    # --------------------------------------------------------
    # Destructive flag fallback
    # --------------------------------------------------------

    if state.get("is_destructive"):
        return "format_answer"

    # --------------------------------------------------------
    # Normal request
    # --------------------------------------------------------

    return "load_schema"


# ============================================================
# ROUTE AFTER CRITIC
# ============================================================

def route_after_critic(state: AgentState):
    """
    Decide whether SQL is accepted, should be retried,
    or should terminate.
    """

    sql_valid = state.get(
        "sql_valid",
        False
    )

    error = state.get(
        "error"
    )

    error_type = state.get(
        "error_type",
        ErrorType.NONE.value
    )

    retry_count = state.get(
        "retry_count",
        0
    )

    # ========================================================
    # SUCCESS
    # ========================================================

    if sql_valid and not error:

        return "format_answer"

    # ========================================================
    # NON-RETRYABLE ERRORS
    # ========================================================
    #
    # These indicate infrastructure / protocol problems
    # rather than a SQL problem that another SQL attempt
    # can reliably fix.
    # ========================================================

    if error_type in {
        ErrorType.CRITIC_ERROR.value,
        ErrorType.SAFETY_BLOCK.value,
        ErrorType.UNKNOWN_ERROR.value,
    }:

        return "format_answer"

    # ========================================================
    # RETRY LIMIT
    # ========================================================

    if retry_count >= MAX_RETRIES:

        return "format_answer"

    # ========================================================
    # RETRY
    # ========================================================

    return "prepare_retry"


# ============================================================
# PREPARE RETRY
# ============================================================

def prepare_retry(state: AgentState) -> dict:
    """
    Save the rejected SQL and prepare another generation attempt.
    """

    current_sql = state.get(
        "sql"
    )

    return {
        "previous_sql": current_sql,

        "retry_count": (
            state.get("retry_count", 0) + 1
        ),

        "sql": None,

        "query_result": None,

        "error": None,

        "error_type": ErrorType.NONE.value,

        "sql_valid": False,
    }


# ============================================================
# BUILD GRAPH
# ============================================================

def build_graph():

    workflow = StateGraph(
        AgentState
    )

    # --------------------------------------------------------
    # NODES
    # --------------------------------------------------------

    workflow.add_node(
        "check_intent",
        check_intent
    )

    workflow.add_node(
        "load_schema",
        load_schema
    )

    workflow.add_node(
        "retrieve_context",
        retrieve_context
    )

    workflow.add_node(
        "generate_sql",
        generate_sql
    )

    workflow.add_node(
        "execute_sql",
        execute_sql
    )

    workflow.add_node(
        "critique_sql",
        critique_sql
    )

    workflow.add_node(
        "prepare_retry",
        prepare_retry
    )

    workflow.add_node(
        "format_answer",
        format_answer
    )

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    workflow.add_edge(
        START,
        "check_intent"
    )

    # --------------------------------------------------------
    # INTENT ROUTING
    # --------------------------------------------------------

    workflow.add_conditional_edges(
        "check_intent",
        route_after_intent,
        {
            "load_schema": "load_schema",
            "format_answer": "format_answer",
        }
    )

    # --------------------------------------------------------
    # NORMAL PIPELINE
    # --------------------------------------------------------

    workflow.add_edge(
        "load_schema",
        "retrieve_context"
    )

    workflow.add_edge(
        "retrieve_context",
        "generate_sql"
    )

    workflow.add_edge(
        "generate_sql",
        "execute_sql"
    )

    workflow.add_edge(
        "execute_sql",
        "critique_sql"
    )

    # --------------------------------------------------------
    # CRITIC ROUTING
    # --------------------------------------------------------

    workflow.add_conditional_edges(
        "critique_sql",
        route_after_critic,
        {
            "prepare_retry": "prepare_retry",
            "format_answer": "format_answer",
        }
    )

    # --------------------------------------------------------
    # RETRY LOOP
    # --------------------------------------------------------

    workflow.add_edge(
        "prepare_retry",
        "generate_sql"
    )

    # --------------------------------------------------------
    # FINAL ANSWER
    # --------------------------------------------------------

    workflow.add_edge(
        "format_answer",
        END
    )

    # --------------------------------------------------------
    # COMPILE
    # --------------------------------------------------------

    return workflow.compile()


# ============================================================
# COMPILED GRAPH
# ============================================================

agent_graph = build_graph()