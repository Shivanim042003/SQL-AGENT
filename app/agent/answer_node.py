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

        return {
            "final_answer": f"Result: {query_result}"
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