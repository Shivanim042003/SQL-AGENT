import asyncio
import logging
import uuid

from mcp.server import MCPServer

from app.agent.graph import agent_graph
from app.core.logging_config import configure_logging


# =========================================================
# Logging
# =========================================================

configure_logging()

logger = logging.getLogger(__name__)


# =========================================================
# MCP Server
# =========================================================

server = MCPServer(
    name="sql-agent",
    version="1.0.0",
    description="MCP interface for the self-correcting SQL agent",
)


# =========================================================
# MCP Tool
# =========================================================

@server.tool(
    name="ask_database",
    description=(
        "Ask a natural-language question about the database. "
        "The request is processed by the self-correcting SQL agent, "
        "including safety checks, schema grounding, SQL generation, "
        "execution, criticism, and retries."
    ),
)
def ask_database(question: str) -> str:

    # -----------------------------------------------------
    # Create unique request ID
    # -----------------------------------------------------

    request_id = str(uuid.uuid4())

    logger.info(
        "request_id=%s | request_started | question=%s",
        request_id,
        question,
    )

    # -----------------------------------------------------
    # Initial Agent State
    # -----------------------------------------------------

    initial_state = {
        "request_id": request_id,

        "question": question,

        "is_destructive": False,

        "schema": "",

        "retrieved_context": "",

        "sql": None,

        "previous_sql": None,

        "query_result": None,

        "error": None,

        "sql_valid": False,

        "critique": "",

        "retry_count": 0,

        "final_answer": None,
    }

    # -----------------------------------------------------
    # Run Agent
    # -----------------------------------------------------

    try:

        result = agent_graph.invoke(initial_state)

        final_answer = result.get("final_answer")

        # -------------------------------------------------
        # Successful request
        # -------------------------------------------------

        if final_answer:

            logger.info(
                "request_id=%s | request_completed | retry_count=%s",
                request_id,
                result.get("retry_count", 0),
            )

            return final_answer

        # -------------------------------------------------
        # Execution failure
        # -------------------------------------------------

        error = result.get("error")

        if error:

            logger.error(
                "request_id=%s | request_failed | error=%s",
                request_id,
                error,
            )

            return f"Agent failed: {error}"

        # -------------------------------------------------
        # SQL verification failure
        # -------------------------------------------------

        critique = result.get("critique")

        if critique:

            logger.warning(
                "request_id=%s | "
                "request_failed_verification | "
                "retry_count=%s | "
                "critique=%s",
                request_id,
                result.get("retry_count", 0),
                critique,
            )

            return (
                "The agent could not produce a valid answer.\n"
                f"Critique: {critique}"
            )

        # -------------------------------------------------
        # No answer
        # -------------------------------------------------

        logger.warning(
            "request_id=%s | request_completed_without_answer",
            request_id,
        )

        return (
            "The agent completed without producing "
            "a final answer."
        )

    # -----------------------------------------------------
    # Unexpected exception
    # -----------------------------------------------------

    except Exception as e:

        logger.exception(
            "request_id=%s | request_exception",
            request_id,
        )

        return f"Agent error: {str(e)}"


# =========================================================
# MCP Entry Point
# =========================================================

async def main():

    logger.info("MCP server starting")

    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())