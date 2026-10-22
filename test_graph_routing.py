from app.agent.graph import route_after_intent


def test_destructive_request_stops():
    assert route_after_intent({"is_destructive": True}) == "format_answer"


def test_safe_request_continues():
    state = {"is_destructive": False, "error_type": "NONE"}
    assert route_after_intent(state) == "load_schema"


def test_failed_safety_check_fails_closed():
    # If the safety LLM itself failed (error or unparseable reply),
    # the pipeline must stop instead of continuing to SQL generation.
    state = {
        "is_destructive": False,
        "error": "Safety intent check failed: boom",
        "error_type": "LLM_ERROR",
    }
    assert route_after_intent(state) == "format_answer"
