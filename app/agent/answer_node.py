from decimal import Decimal

from app.core.timing import measure_latency


def _clean_result(value):
    """
    Convert database-specific numeric values into
    clean Python values for the final response.

    Decimal values are converted to strings instead of floats
    so that we don't lose precision.
    """

    # --------------------------------------------------------
    # DECIMAL
    # --------------------------------------------------------

    if isinstance(value, Decimal):
        return str(value)

    # --------------------------------------------------------
    # LIST
    # --------------------------------------------------------

    if isinstance(value, list):
        return [
            _clean_result(item)
            for item in value
        ]

    # --------------------------------------------------------
    # DICTIONARY
    # --------------------------------------------------------

    if isinstance(value, dict):
        return {
            key: _clean_result(val)
            for key, val in value.items()
        }

    # --------------------------------------------------------
    # OTHER VALUES
    # --------------------------------------------------------

    return value


def format_answer(state):
    """
    Produce the final human-readable answer
    for every terminal path in the workflow.

    Latency:
        Measures the answer-formatting stage and stores it under:

            latencies["answer"]

    Retry latency:
        Preserves the retry_latencies dictionary generated
        by earlier nodes.
    """

    # --------------------------------------------------------
    # Preserve cumulative latency
    # --------------------------------------------------------

    latencies = dict(
        state.get(
            "latencies",
            {}
        )
    )

    # --------------------------------------------------------
    # Preserve per-attempt latency
    # --------------------------------------------------------

    retry_latencies = {
        key: dict(value)
        for key, value in state.get(
            "retry_latencies",
            {}
        ).items()
    }

    # ========================================================
    # DESTRUCTIVE REQUEST
    # ========================================================

    if state.get(
        "is_destructive"
    ):

        with measure_latency(
            latencies,
            "answer"
        ):

            final_answer = (
                "I can't perform that request because this system only "
                "allows read-only database operations."
            )

        return {
            "final_answer": final_answer,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # ========================================================
    # SUCCESSFUL QUERY
    # ========================================================

    if (
        state.get("sql_valid")
        and not state.get("error")
    ):

        with measure_latency(
            latencies,
            "answer"
        ):

            query_result = state.get(
                "query_result"
            )

            # Clean database-specific values such as Decimal
            clean_result = _clean_result(
                query_result
            )

            final_answer = (
                f"Result: {clean_result}"
            )

        return {
            "final_answer": final_answer,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # ========================================================
    # PIPELINE FAILURE
    # ========================================================

    issue = (
        state.get("critique")
        or state.get("error")
        or "Unable to produce a verified SQL answer."
    )

    with measure_latency(
        latencies,
        "answer"
    ):

        final_answer = (
            f"I wasn't able to produce a verified answer. "
            f"Reason: {issue}"
        )

    return {
        "final_answer": final_answer,
        "latencies": latencies,
        "retry_latencies": retry_latencies,
    }