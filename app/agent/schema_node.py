from app.agent.state import AgentState
from app.execution.schema_info import get_schema_summary
from app.core.timing import measure_latency


def load_schema(state: AgentState) -> dict:
    """
    Load the current live database schema.

    The time spent loading the schema is recorded under
    the "schema" latency key.
    """

    # Preserve latency measurements from previous nodes.
    latencies = dict(
        state.get("latencies", {})
    )

    # Measure live schema introspection.
    with measure_latency(
        latencies,
        "schema"
    ):
        schema = get_schema_summary()

    return {
        "schema": schema,
        "latencies": latencies,
    }