from decimal import Decimal


def _clean_result(value):
    """
    Convert database-specific numeric values into
    clean Python values for the final response.
    """

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, list):
        return [_clean_result(item) for item in value]

    if isinstance(value, dict):
        return {
            key: _clean_result(val)
            for key, val in value.items()
        }

    return value


def format_answer(state):
    """
    Produce the final human-readable answer
    for every terminal path in the workflow.
    """

    # --------------------------------------------------------
    # DESTRUCTIVE REQUEST
    # --------------------------------------------------------

    if state.get("is_destructive"):
        return {
            "final_answer": (
                "I can't perform that request because this system only "
                "allows read-only database operations."
            )
        }

    # --------------------------------------------------------
    # SUCCESSFUL QUERY
    # --------------------------------------------------------

    if state.get("sql_valid") and not state.get("error"):

        query_result = state.get("query_result")

        clean_result = _clean_result(query_result)

        return {
            "final_answer": f"Result: {clean_result}"
        }

    # --------------------------------------------------------
    # PIPELINE FAILURE
    # --------------------------------------------------------

    issue = (
        state.get("critique")
        or state.get("error")
        or "Unable to produce a verified SQL answer."
    )

    return {
        "final_answer": (
            f"I wasn't able to produce a verified answer. "
            f"Reason: {issue}"
        )
    }