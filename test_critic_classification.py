from unittest.mock import patch

from app.agent.critic_node import critique_sql


def base_state():
    return {
        "request_id": "test-request",
        "question": "How many purchase events are there?",
        "is_destructive": False,
        "schema": "events(id, event_type, session_id)",
        "retrieved_context": "",
        "sql": "SELECT COUNT(*) FROM events WHERE event_type = 'purchase';",
        "previous_sql": None,
        "query_result": [{"count": 100}],
        "error": None,
        "error_type": "NONE",
        "sql_valid": False,
        "critique": "",
        "retry_count": 0,
        "final_answer": None,
    }


class FakeCriticClientError:

    def complete(self, system_prompt, messages):
        raise RuntimeError("Test critic failure")


class FakeCriticClientBadResponse:

    def complete(self, system_prompt, messages):

        class Response:
            content = "This is not valid JSON"

        return Response()


class FakeCriticClientSuccess:

    def complete(self, system_prompt, messages):

        class Response:
            content = '{"valid": true, "feedback": ""}'

        return Response()


def test_critic_llm_error():

    print("\nTEST 1: CRITIC_ERROR - LLM failure")
    print("--------------------------------------")

    with patch(
        "app.agent.critic_node.get_llm_client",
        return_value=FakeCriticClientError()
    ):
        result = critique_sql(base_state())

    print(f"error_type: {result.get('error_type')}")
    print(f"critique: {result.get('critique')}")

    assert result["error_type"] == "CRITIC_ERROR"

    print("PASS")


def test_critic_bad_response():

    print("\nTEST 2: CRITIC_ERROR - invalid response")
    print("--------------------------------------")

    with patch(
        "app.agent.critic_node.get_llm_client",
        return_value=FakeCriticClientBadResponse()
    ):
        result = critique_sql(base_state())

    print(f"error_type: {result.get('error_type')}")
    print(f"critique: {result.get('critique')}")

    assert result["error_type"] == "CRITIC_ERROR"

    print("PASS")


def test_critic_success():

    print("\nTEST 3: NONE - successful critic")
    print("--------------------------------------")

    with patch(
        "app.agent.critic_node.get_llm_client",
        return_value=FakeCriticClientSuccess()
    ):
        result = critique_sql(base_state())

    print(f"error_type: {result.get('error_type')}")
    print(f"sql_valid: {result.get('sql_valid')}")
    print(f"critique: {result.get('critique')}")

    assert result["error_type"] == "NONE"
    assert result["sql_valid"] is True

    print("PASS")


def test_execution_error_preserved():

    print("\nTEST 4: Preserve SQL_TIMEOUT")
    print("--------------------------------------")

    state = base_state()

    state["error"] = "canceling statement due to statement timeout"
    state["error_type"] = "SQL_TIMEOUT"

    result = critique_sql(state)

    print(f"error_type: {result.get('error_type')}")
    print(f"critique: {result.get('critique')}")

    assert result["error_type"] == "SQL_TIMEOUT"

    print("PASS")


def main():

    test_critic_llm_error()
    test_critic_bad_response()
    test_critic_success()
    test_execution_error_preserved()

    print("\nAll critic classification tests passed.")


if __name__ == "__main__":
    main()
    