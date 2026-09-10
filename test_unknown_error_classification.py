from app.agent.executor_node import execute_sql
from app.core.error_types import ErrorType


def test_unknown_error():

    import app.agent.executor_node as executor_node

    original_connect = executor_node.psycopg2.connect

    class BrokenConnection:

        def cursor(self):
            raise RuntimeError(
                "Unexpected test failure"
            )

    try:

        executor_node.psycopg2.connect = (
            lambda _: BrokenConnection()
        )

        state = {
            "sql": "SELECT 1"
        }

        result = execute_sql(
            state
        )

        print()
        print(
            "TEST: UNKNOWN_ERROR"
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
            == ErrorType.UNKNOWN_ERROR.value
        )

        print("PASS")

    finally:

        executor_node.psycopg2.connect = (
            original_connect
        )


if __name__ == "__main__":

    test_unknown_error()

    print()
    print(
        "Unknown error classification test passed."
    )