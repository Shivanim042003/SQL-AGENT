from app.agent.state import AgentState
from app.execution.schema_info import get_schema_summary


def load_schema(state: AgentState) -> dict:
    """Load the current live database schema."""

    schema = get_schema_summary()

    return {
        "schema": schema
    }