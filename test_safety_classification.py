from app.agent.intent_node import check_intent
from app.core.error_types import ErrorType


# ============================================================
# FAKE LLM
# ============================================================

class FakeResponse:

    def __init__(self, content):
        self.content = content


class FakeLLM:

    def __init__(self, response):
        self.response = response

    def complete(self, system_prompt, messages):
        return FakeResponse(
            self.response
        )


# ============================================================
# TEST 1
# ============================================================

def test_destructive_request():

    import app.agent.intent_node as intent_node

    original = intent_node.get_llm_client

    try:

        intent_node.get_llm_client = lambda: FakeLLM(
            '{"is_destructive": true}'
        )

        state = {
            "question": "delete all users"
        }

        result = check_intent(
            state
        )

        print()
        print(
            "TEST 1: SAFETY_BLOCK - destructive request"
        )
        print("--------------------------------------")
        print(
            "is_destructive:",
            result["is_destructive"]
        )
        print(
            "error_type:",
            result["error_type"]
        )

        assert result["is_destructive"] is True

        assert (
            result["error_type"]
            == ErrorType.SAFETY_BLOCK.value
        )

        print("PASS")

    finally:

        intent_node.get_llm_client = original


# ============================================================
# TEST 2
# ============================================================

def test_safe_request():

    import app.agent.intent_node as intent_node

    original = intent_node.get_llm_client

    try:

        intent_node.get_llm_client = lambda: FakeLLM(
            '{"is_destructive": false}'
        )

        state = {
            "question": "how many users are there?"
        }

        result = check_intent(
            state
        )

        print()
        print(
            "TEST 2: NONE - safe request"
        )
        print("--------------------------------------")
        print(
            "is_destructive:",
            result["is_destructive"]
        )
        print(
            "error_type:",
            result["error_type"]
        )

        assert result["is_destructive"] is False

        assert (
            result["error_type"]
            == ErrorType.NONE.value
        )

        print("PASS")

    finally:

        intent_node.get_llm_client = original


# ============================================================
# TEST 3
# ============================================================

def test_intent_llm_failure():

    import app.agent.intent_node as intent_node

    original = intent_node.get_llm_client

    class FailingLLM:

        def complete(
            self,
            system_prompt,
            messages
        ):
            raise RuntimeError(
                "Test intent failure"
            )

    try:

        intent_node.get_llm_client = (
            lambda: FailingLLM()
        )

        state = {
            "question": "how many users are there?"
        }

        result = check_intent(
            state
        )

        print()
        print(
            "TEST 3: LLM_ERROR - intent failure"
        )
        print("--------------------------------------")
        print(
            "error_type:",
            result["error_type"]
        )
        print(
            "error:",
            result["error"]
        )

        assert (
            result["error_type"]
            == ErrorType.LLM_ERROR.value
        )

        print("PASS")

    finally:

        intent_node.get_llm_client = original


# ============================================================
# TEST 4
# ============================================================

def test_invalid_intent_response():

    import app.agent.intent_node as intent_node

    original = intent_node.get_llm_client

    try:

        intent_node.get_llm_client = lambda: FakeLLM(
            "This is not valid JSON"
        )

        state = {
            "question": "how many users are there?"
        }

        result = check_intent(
            state
        )

        print()
        print(
            "TEST 4: LLM_ERROR - invalid intent response"
        )
        print("--------------------------------------")
        print(
            "error_type:",
            result["error_type"]
        )

        assert (
            result["error_type"]
            == ErrorType.LLM_ERROR.value
        )

        print("PASS")

    finally:

        intent_node.get_llm_client = original


# ============================================================
# MAIN
# ============================================================

def main():

    test_destructive_request()

    test_safe_request()

    test_intent_llm_failure()

    test_invalid_intent_response()

    print()
    print(
        "All safety classification tests passed."
    )


if __name__ == "__main__":
    main()