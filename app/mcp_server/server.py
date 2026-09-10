import asyncio
import logging
import uuid

from mcp.server import MCPServer

from app.agent.graph import invoke_agent
from app.core.logging_config import configure_logging
from app.core.metrics import request_metrics
from app.core.request_timeout import (
    RequestTimeoutError,
    run_with_timeout,
)
from app.core.validation import (
    RequestValidationError,
    validate_question,
)
from app.metrics.repository import (
    delete_old_request_metrics,
    get_error_statistics,
    get_recent_request_metrics,
    get_request_statistics,
    save_request_metrics,
)


# =========================================================
# Logging
# =========================================================

configure_logging()

logger = logging.getLogger(__name__)


# =========================================================
# Helpers
# =========================================================

def persist_request_metrics(
    request_id: str,
    retry_count: int,
    error_type: str,
    total_latency: float,
    success: bool,
):
    """
    Persist request metrics without allowing metrics failures
    to affect the actual agent request.
    """

    try:
        save_request_metrics(
            request_id=request_id,
            retry_count=retry_count,
            error_type=error_type,
            total_latency=total_latency,
            success=success,
        )

    except Exception:
        logger.exception(
            "request_id=%s | metrics_persistence_failed",
            request_id,
        )


# =========================================================
# MCP Server
# =========================================================

server = MCPServer(
    name="sql-agent",
    version="1.0.0",
    description="MCP interface for the self-correcting SQL agent",
)


# =========================================================
# MCP Tool - Ask Database
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
    # Validate request
    # -----------------------------------------------------

    try:
        question = validate_question(question)

    except RequestValidationError as e:

        logger.warning(
            "request_rejected | reason=%s",
            str(e),
        )

        return f"Invalid request: {e}"

    # -----------------------------------------------------
    # Record incoming request
    # -----------------------------------------------------

    request_metrics.record_request()

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

        "error_type": "NONE",

        "sql_valid": False,

        "critique": "",

        "retry_count": 0,

        "final_answer": None,

        # Production latency tracking
        "latencies": {},

        # Per-attempt latency tracking
        "retry_latencies": {},
    }

    # -----------------------------------------------------
    # Run Agent
    # -----------------------------------------------------

    try:

        try:

            result = run_with_timeout(
                invoke_agent,
                initial_state,
            )

        except RequestTimeoutError as e:

            request_metrics.record_timeout()

            persist_request_metrics(
                request_id=request_id,
                retry_count=0,
                error_type="SQL_TIMEOUT",
                total_latency=0.0,
                success=False,
            )

            logger.error(
                "request_id=%s | "
                "request_timeout | "
                "error_type=SQL_TIMEOUT | "
                "error=%s",
                request_id,
                str(e),
            )

            return f"Agent timeout: {e}"

        # -------------------------------------------------
        # Request metrics
        # -------------------------------------------------

        retry_count = result.get(
            "retry_count",
            0,
        )

        error_type = result.get(
            "error_type",
            "NONE",
        )

        total_latency = result.get(
            "latencies",
            {},
        ).get(
            "total",
            0.0,
        )

        request_metrics.record_retries(
            retry_count
        )

        final_answer = result.get(
            "final_answer"
        )

        # -------------------------------------------------
        # Successful request
        # -------------------------------------------------

        if final_answer:

            request_metrics.record_success()

            persist_request_metrics(
                request_id=request_id,
                retry_count=retry_count,
                error_type=error_type,
                total_latency=total_latency,
                success=True,
            )

            logger.info(
                "request_id=%s | "
                "request_completed | "
                "retry_count=%s | "
                "error_type=%s | "
                "total_latency=%s",
                request_id,
                retry_count,
                error_type,
                total_latency,
            )

            return final_answer

        # -------------------------------------------------
        # Safety block
        # -------------------------------------------------

        if error_type == "SAFETY_BLOCK":

            request_metrics.record_safety_block()

            persist_request_metrics(
                request_id=request_id,
                retry_count=retry_count,
                error_type=error_type,
                total_latency=total_latency,
                success=False,
            )

            logger.warning(
                "request_id=%s | "
                "request_safety_block | "
                "error_type=SAFETY_BLOCK",
                request_id,
            )

            return (
                result.get("final_answer")
                or "Request blocked for safety reasons."
            )

        # -------------------------------------------------
        # Agent execution failure
        # -------------------------------------------------

        error = result.get("error")

        if error:

            request_metrics.record_failure()

            persist_request_metrics(
                request_id=request_id,
                retry_count=retry_count,
                error_type=error_type,
                total_latency=total_latency,
                success=False,
            )

            logger.error(
                "request_id=%s | "
                "request_failed | "
                "error_type=%s | "
                "error=%s | "
                "total_latency=%s",
                request_id,
                error_type,
                error,
                total_latency,
            )

            return f"Agent failed: {error}"

        # -------------------------------------------------
        # SQL verification failure
        # -------------------------------------------------

        critique = result.get("critique")

        if critique:

            request_metrics.record_failure()

            persist_request_metrics(
                request_id=request_id,
                retry_count=retry_count,
                error_type=error_type,
                total_latency=total_latency,
                success=False,
            )

            logger.warning(
                "request_id=%s | "
                "request_failed_verification | "
                "error_type=%s | "
                "retry_count=%s | "
                "critique=%s | "
                "total_latency=%s",
                request_id,
                error_type,
                retry_count,
                critique,
                total_latency,
            )

            return (
                "The agent could not produce a valid answer.\n"
                f"Critique: {critique}"
            )

        # -------------------------------------------------
        # No answer
        # -------------------------------------------------

        request_metrics.record_failure()

        persist_request_metrics(
            request_id=request_id,
            retry_count=retry_count,
            error_type=error_type,
            total_latency=total_latency,
            success=False,
        )

        logger.warning(
            "request_id=%s | "
            "request_completed_without_answer | "
            "error_type=%s | "
            "total_latency=%s",
            request_id,
            error_type,
            total_latency,
        )

        return (
            "The agent completed without producing "
            "a final answer."
        )

    # -----------------------------------------------------
    # Unexpected exception
    # -----------------------------------------------------

    except Exception as e:

        request_metrics.record_failure()

        persist_request_metrics(
            request_id=request_id,
            retry_count=0,
            error_type="UNKNOWN_ERROR",
            total_latency=0.0,
            success=False,
        )

        logger.exception(
            "request_id=%s | "
            "request_exception | "
            "error_type=UNKNOWN_ERROR",
            request_id,
        )

        return f"Agent error: {str(e)}"


# =========================================================
# MCP Tool - Get Metrics
# =========================================================

@server.tool(
    name="get_metrics",
    description=(
        "Get current runtime metrics, historical aggregate "
        "statistics, error-type statistics, and recent "
        "persisted request metrics."
    ),
)
def get_metrics() -> str:

    # -----------------------------------------------------
    # Runtime metrics
    # -----------------------------------------------------

    runtime_metrics = request_metrics.snapshot()

    # -----------------------------------------------------
    # Historical aggregate statistics
    # -----------------------------------------------------

    try:

        historical_statistics = get_request_statistics()

    except Exception:

        logger.exception(
            "metrics_statistics_query_failed"
        )

        historical_statistics = {}

    # -----------------------------------------------------
    # Error statistics
    # -----------------------------------------------------

    try:

        error_statistics = get_error_statistics()

    except Exception:

        logger.exception(
            "metrics_error_statistics_query_failed"
        )

        error_statistics = {}

    # -----------------------------------------------------
    # Recent persisted requests
    # -----------------------------------------------------

    try:

        recent_requests = get_recent_request_metrics(
            limit=20
        )

    except Exception:

        logger.exception(
            "metrics_history_query_failed"
        )

        recent_requests = []

    # -----------------------------------------------------
    # Log snapshot
    # -----------------------------------------------------

    logger.info(
        "metrics_snapshot | "
        "runtime=%s | "
        "historical=%s | "
        "errors=%s | "
        "recent_requests=%s",
        runtime_metrics,
        historical_statistics,
        error_statistics,
        len(recent_requests),
    )

    # -----------------------------------------------------
    # Return metrics
    # -----------------------------------------------------

    return str(
        {
            "runtime_metrics": runtime_metrics,
            "historical_statistics": historical_statistics,
            "error_statistics": error_statistics,
            "recent_requests": recent_requests,
        }
    )


# =========================================================
# MCP Tool - Cleanup Metrics
# =========================================================

@server.tool(
    name="cleanup_metrics",
    description=(
        "Delete persisted request metrics older than the "
        "specified retention period."
    ),
)
def cleanup_metrics(
    retention_days: int = 30,
) -> str:

    # -----------------------------------------------------
    # Cleanup metrics
    # -----------------------------------------------------

    try:

        deleted_rows = delete_old_request_metrics(
            retention_days=retention_days
        )

        logger.info(
            "metrics_cleanup | "
            "retention_days=%s | "
            "deleted_rows=%s",
            retention_days,
            deleted_rows,
        )

        return (
            f"Metrics cleanup completed. "
            f"Deleted {deleted_rows} records older than "
            f"{retention_days} days."
        )

    except ValueError as e:

        logger.warning(
            "metrics_cleanup_rejected | reason=%s",
            str(e),
        )

        return f"Invalid retention period: {e}"

    except Exception as e:

        logger.exception(
            "metrics_cleanup_failed"
        )

        return f"Metrics cleanup failed: {e}"


# =========================================================
# MCP Entry Point
# =========================================================

async def main():

    logger.info("MCP server starting")

    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())