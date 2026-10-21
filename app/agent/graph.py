from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState

from app.agent.intent_node import check_intent
from app.agent.schema_node import load_schema
from app.agent.retrieval_node import retrieve_context
from app.agent.sql_generator import generate_sql
from app.agent.executor_node import execute_sql
from app.agent.critic_node import critique_sql
from app.agent.fast_path import critique_with_fast_path
from app.agent.answer_node import format_answer

from app.core.timing import measure_latency


# ============================================================
# CONFIGURATION
# ============================================================

MAX_RETRIES = 2


# ============================================================
# ROUTING FUNCTIONS
# ============================================================

def route_after_intent(state: AgentState):
    """
    Decide whether the request is safe to continue.
    """

    if state.get("is_destructive"):
        return "format_answer"

    return "load_schema"


def route_after_critic(state: AgentState):
    """
    Decide whether SQL is accepted or needs another attempt.
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
        "NONE"
    )

    retry_count = state.get(
        "retry_count",
        0
    )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    if sql_valid and not error:
        return "format_answer"

    # --------------------------------------------------------
    # DO NOT RETRY CERTAIN FAILURES
    # --------------------------------------------------------

    if error_type in {
        "CRITIC_ERROR",
        "SAFETY_BLOCK",
        "UNKNOWN_ERROR",
    }:
        return "format_answer"

    # --------------------------------------------------------
    # RETRY LIMIT
    # --------------------------------------------------------

    if retry_count >= MAX_RETRIES:
        return "format_answer"

    # --------------------------------------------------------
    # RETRY
    # --------------------------------------------------------

    return "prepare_retry"


# ============================================================
# RETRY PREPARATION
# ============================================================

def prepare_retry(state: AgentState) -> dict:
    """
    Save rejected SQL and increment retry count.

    Existing latency measurements are preserved.
    """

    current_sql = state.get(
        "sql"
    )

    return {
        "previous_sql": current_sql,

        "retry_count": (
            state.get(
                "retry_count",
                0
            )
            + 1
        ),

        "sql": None,

        "query_result": None,

        "error": None,

        "error_type": "NONE",

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
        critique_with_fast_path
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
    # SAFETY ROUTING
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

    return workflow.compile()


# ============================================================
# COMPILED GRAPH
# ============================================================

agent_graph = build_graph()


# ============================================================
# TIMED AGENT INVOCATION
# ============================================================

def invoke_agent(initial_state: AgentState) -> dict:
    """
    Invoke the complete SQL agent.

    Measures:

        - individual stage latency
        - cumulative retry latency
        - total request latency
    """

    # --------------------------------------------------------
    # Initial cumulative latency
    # --------------------------------------------------------

    latencies = dict(
        initial_state.get(
            "latencies",
            {}
        )
    )

    # --------------------------------------------------------
    # Initial per-attempt latency
    # --------------------------------------------------------

    retry_latencies = {
        key: dict(value)
        for key, value in initial_state.get(
            "retry_latencies",
            {}
        ).items()
    }

    # --------------------------------------------------------
    # Initial state
    # --------------------------------------------------------

    start_state = {
        **initial_state,

        "latencies": latencies,

        "retry_latencies": retry_latencies,
    }

    # --------------------------------------------------------
    # Total request timer
    # --------------------------------------------------------

    with measure_latency(
        latencies,
        "total"
    ):
        result = agent_graph.invoke(
            start_state
        )

    # --------------------------------------------------------
    # Get latency data generated by graph
    # --------------------------------------------------------

    graph_latencies = dict(
        result.get(
            "latencies",
            {}
        )
    )

    graph_retry_latencies = {
        key: dict(value)
        for key, value in result.get(
            "retry_latencies",
            {}
        ).items()
    }

    # --------------------------------------------------------
    # Add actual end-to-end total
    # --------------------------------------------------------

    if "total" in latencies:
        graph_latencies["total"] = latencies["total"]

    # --------------------------------------------------------
    # Final latency state
    # --------------------------------------------------------

    result["latencies"] = graph_latencies

    result["retry_latencies"] = (
        graph_retry_latencies
    )

    return result