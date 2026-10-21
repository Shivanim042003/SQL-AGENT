from unittest.mock import patch

from app.agent.sql_generator import generate_sql


def base_state():
    return {
        "request_id": "test-request",
        "question": "How many purchase events are there?",
        "is_destructive": False,
        "schema": "events(id, event_type, session_id)",
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
    }


class FakeClientLLMError:

    def complete(self, system_prompt, messages, **kwargs):
        raise RuntimeError("Test LLM failure")


class FakeClientBadResponse:

    def complete(self, system_prompt, messages, **kwargs):

        class Response:
            content = "This is not valid SQL JSON"

        return Response()


def test_llm_error():

    print("\nTEST 1: LLM_ERROR")
    print("--------------------------------------")

    with patch(
        "app.agent.sql_generator.get_llm_client",
        return_value=FakeClientLLMError()
    ):
        result = generate_sql(base_state())

    print(f"error_type: {result.get('error_type')}")
    print(f"error: {result.get('error')}")

    assert result["error_type"] == "LLM_ERROR"
    assert "Test LLM failure" in result["error"]

    print("PASS")


def test_sql_generation_error():

    print("\nTEST 2: SQL_GENERATION_ERROR")
    print("--------------------------------------")

    with patch(
        "app.agent.sql_generator.get_llm_client",
        return_value=FakeClientBadResponse()
    ):
        result = generate_sql(base_state())

    print(f"error_type: {result.get('error_type')}")
    print(f"error: {result.get('error')}")

    assert result["error_type"] == "SQL_GENERATION_ERROR"

    print("PASS")


def main():

    test_llm_error()

    test_sql_generation_error()

    print("\nAll generator classification tests passed.")


if __name__ == "__main__":
    main()
