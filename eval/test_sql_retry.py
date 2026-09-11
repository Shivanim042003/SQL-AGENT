import os
import sys


# ------------------------------------------------------------
# Allow imports from project root
# ------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)


# ------------------------------------------------------------
# Imports
# ------------------------------------------------------------

from app.agent.intent_node import check_intent
from app.agent.schema_node import load_schema
from app.agent.retrieval_node import retrieve_context
from app.agent.executor_node import execute_sql
from app.agent.critic_node import critique_sql


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

# Initial attempt + 2 retries = maximum 3 attempts
MAX_ATTEMPTS = 3

# Independently verified ground truth for:
# "What is the conversion rate?"
EXPECTED_CONVERSION_RATE = 26.6603007807744379


# ------------------------------------------------------------
# Deterministic SQL test cases
# ------------------------------------------------------------

TEST_SQL_ATTEMPTS = [
    {
        "sql": """
            SELECT
                COUNT(DISTINCT session_id) * 100.0
                / COUNT(DISTINCT session_id) FILTER (
                    WHERE event_type = 'purchase'
                )
            FROM events
            WHERE event_type IN ('cart', 'purchase')
            GROUP BY 1
        """.strip(),

        "description": (
            "Invalid SQL: aggregate expression used in GROUP BY."
        ),
    },
    {
        "sql": """
            SELECT
                COUNT(
                    DISTINCT CASE
                        WHEN event_type = 'purchase'
                        THEN session_id
                    END
                ) * 100.0
                / COUNT(DISTINCT session_id)
            FROM events
            WHERE event_type IN ('cart', 'purchase')
        """.strip(),

        "description": (
            "Executable SQL with incorrect business logic."
        ),
    },
    {
        "sql": """
            SELECT
                COUNT(
                    DISTINCT CASE
                        WHEN event_type = 'purchase'
                        THEN session_id
                    END
                ) * 100.0
                / COUNT(DISTINCT session_id)
            FROM events
        """.strip(),

        "description": (
            "Correct SQL for the conversion-rate definition."
        ),
    },
]


# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def print_line():
    print("=" * 80)


def print_attempt_header(attempt: int):
    print()
    print_line()
    print(f"SQL ATTEMPT {attempt}")
    print_line()


def extract_result_value(query_result):
    """
    Extract the first scalar value from a single-row result.
    """

    if not query_result:
        return None

    first_row = query_result[0]

    if not first_row:
        return None

    return next(
        iter(first_row.values())
    )


def result_matches_ground_truth(query_result):
    """
    Compare the SQL result with independently verified
    conversion-rate ground truth.
    """

    actual_value = extract_result_value(
        query_result
    )

    if actual_value is None:
        return False, None

    actual_value = float(actual_value)

    matches = abs(
        actual_value - EXPECTED_CONVERSION_RATE
    ) <= 1e-9

    return matches, actual_value


# ------------------------------------------------------------
# Deterministic SQL Generator
# ------------------------------------------------------------

def generate_test_sql(state, attempt_index):
    """
    Return a predetermined SQL statement for the current
    retry attempt.

    This intentionally avoids calling the LLM so that the
    regression test does not depend on model randomness.
    """

    if attempt_index >= len(TEST_SQL_ATTEMPTS):
        raise RuntimeError(
            "No deterministic SQL is defined for this attempt."
        )

    sql = TEST_SQL_ATTEMPTS[
        attempt_index
    ]["sql"]

    return {
        "sql": sql,
        "error": None,
        "error_type": "NONE",
    }


# ------------------------------------------------------------
# Main Pipeline
# ------------------------------------------------------------

def main():

    print_line()
    print(
        "DETERMINISTIC SQL GENERATION + "
        "EXECUTION + CRITIC RETRY TEST"
    )
    print_line()

    # --------------------------------------------------------
    # Initial Agent State
    # --------------------------------------------------------

    state = {
        "question": "What is the conversion rate?",

        "schema": "",

        "retrieved_context": "",

        "sql": None,

        "previous_sql": None,

        "query_result": None,

        "error": None,

        "error_type": "NONE",

        "sql_valid": False,

        "critique": "",

        "is_destructive": False,

        "retry_count": 0,

        "final_answer": None,

        "latencies": {},

        "retry_latencies": {},
    }

    # --------------------------------------------------------
    # STEP 1: SAFETY CHECK
    # --------------------------------------------------------

    print()
    print("SAFETY CHECK...")

    state.update(
        check_intent(state)
    )

    print(
        "Is destructive:",
        state["is_destructive"]
    )

    if state["is_destructive"]:

        print()
        print("STOPPING PIPELINE.")
        print(
            "Destructive requests are not allowed."
        )

        raise AssertionError(
            "Safe retry test question was classified as destructive."
        )

    # --------------------------------------------------------
    # STEP 2: LOAD DATABASE SCHEMA
    # --------------------------------------------------------

    print()
    print("LOADING SCHEMA...")

    state.update(
        load_schema(state)
    )

    if not state.get("schema"):

        raise AssertionError(
            "Schema could not be loaded."
        )

    print(
        "Schema loaded successfully."
    )

    # --------------------------------------------------------
    # STEP 3: RETRIEVE BUSINESS CONTEXT
    # --------------------------------------------------------

    print()
    print("RETRIEVING BUSINESS CONTEXT...")

    state.update(
        retrieve_context(state)
    )

    print(
        "Business context retrieved successfully."
    )

    # --------------------------------------------------------
    # STEP 4: DETERMINISTIC RETRY LOOP
    # --------------------------------------------------------

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):

        print_attempt_header(
            attempt
        )

        attempt_index = attempt - 1

        # ----------------------------------------------------
        # GENERATE SQL
        # ----------------------------------------------------

        if attempt == 1:

            print()
            print(
                "GENERATING DETERMINISTIC TEST SQL..."
            )

        else:

            print()
            print(
                "REGENERATING SQL USING "
                "PREVIOUS SQL + CRITIQUE..."
            )

            print()
            print("-" * 80)
            print("RETRY INFORMATION")
            print("-" * 80)

            print()
            print("PREVIOUS SQL:")
            print(
                state.get("previous_sql")
            )

            print()
            print("CRITIQUE:")
            print(
                state.get("critique")
            )

        # ----------------------------------------------------
        # Reset attempt-specific state
        #
        # Preserve:
        # - previous_sql
        # - critique
        # - retry_count
        # - latency information
        # ----------------------------------------------------

        state["sql"] = None
        state["query_result"] = None
        state["error"] = None
        state["error_type"] = "NONE"
        state["sql_valid"] = False

        # ----------------------------------------------------
        # Generate deterministic SQL
        # ----------------------------------------------------

        generation_result = generate_test_sql(
            state,
            attempt_index,
        )

        state.update(
            generation_result
        )

        print()
        print("GENERATED SQL:")
        print()
        print(
            state["sql"]
        )

        print()
        print("TEST CASE:")
        print(
            TEST_SQL_ATTEMPTS[
                attempt_index
            ]["description"]
        )

        # ----------------------------------------------------
        # EXECUTE SQL
        # ----------------------------------------------------

        print()
        print("-" * 80)
        print("EXECUTING SQL...")
        print("-" * 80)

        execution_result = execute_sql(
            state
        )

        state.update(
            execution_result
        )

        if state.get("error"):

            print()
            print("EXECUTION ERROR:")
            print(
                state["error"]
            )

        else:

            print()
            print(
                "EXECUTION SUCCESSFUL."
            )

            print()
            print("QUERY RESULT:")
            print(
                state["query_result"]
            )

        # ----------------------------------------------------
        # CRITIC REVIEW
        # ----------------------------------------------------

        print()
        print("-" * 80)
        print("CRITIC REVIEW...")
        print("-" * 80)

        critic_result = critique_sql(
            state
        )

        state.update(
            critic_result
        )

        print()
        print("VALID:")
        print(
            state["sql_valid"]
        )

        print()
        print("CRITIQUE:")
        print(
            state["critique"]
        )

        # ----------------------------------------------------
        # Candidate success
        # ----------------------------------------------------

        if (
            state["sql_valid"]
            and not state.get("error")
        ):

            print()
            print(
                "CRITIC ACCEPTED THE SQL."
            )

            # ------------------------------------------------
            # Independent ground-truth validation
            # ------------------------------------------------

            matches_ground_truth, actual_value = (
                result_matches_ground_truth(
                    state["query_result"]
                )
            )

            print()
            print(
                "EXPECTED CONVERSION RATE:"
            )
            print(
                EXPECTED_CONVERSION_RATE
            )

            print()
            print(
                "ACTUAL CONVERSION RATE:"
            )
            print(
                actual_value
            )

            # ------------------------------------------------
            # Correct final answer
            # ------------------------------------------------

            if matches_ground_truth:

                print()
                print_line()
                print(
                    "PIPELINE SUCCESSFUL"
                )
                print_line()

                print()
                print("QUESTION:")
                print(
                    state["question"]
                )

                print()
                print("FINAL SQL:")
                print(
                    state["sql"]
                )

                print()
                print("FINAL RESULT:")
                print(
                    state["query_result"]
                )

                print()
                print("RETRY COUNT:")
                print(
                    state["retry_count"]
                )

                # ------------------------------------------------
                # Regression assertions
                # ------------------------------------------------

                assert attempt > 1, (
                    "Retry mechanism was not exercised."
                )

                assert state["retry_count"] == (
                    attempt - 1
                ), (
                    "Retry count does not match "
                    "the number of retries performed."
                )

                assert state["sql_valid"] is True, (
                    "Final SQL should be valid."
                )

                assert not state.get("error"), (
                    "Final attempt should not contain an error."
                )

                assert actual_value is not None, (
                    "Final result should contain a scalar value."
                )

                assert abs(
                    actual_value
                    - EXPECTED_CONVERSION_RATE
                ) <= 1e-9, (
                    "Final result does not match "
                    "database ground truth."
                )

                print()
                print(
                    "DETERMINISTIC RETRY TEST PASSED"
                )

                print(
                    f"Successful on attempt {attempt} "
                    f"after {state['retry_count']} retry(s)."
                )

                return

            # ------------------------------------------------
            # Critic accepted incorrect result
            # ------------------------------------------------

            print()
            print(
                "CRITIC ACCEPTED AN INCORRECT RESULT."
            )

            print(
                "Independent ground-truth validation "
                "rejected this attempt."
            )

            if attempt < MAX_ATTEMPTS:

                state["previous_sql"] = (
                    state["sql"]
                )

                state["critique"] = (
                    "Independent ground-truth validation failed. "
                    f"Expected conversion rate "
                    f"{EXPECTED_CONVERSION_RATE}, "
                    f"but the generated SQL returned "
                    f"{actual_value}."
                )

                state["retry_count"] = attempt

                continue

            raise AssertionError(
                "Critic accepted SQL whose result "
                "does not match ground truth."
            )

        # ----------------------------------------------------
        # Prepare retry
        # ----------------------------------------------------

        if attempt < MAX_ATTEMPTS:

            state["previous_sql"] = (
                state["sql"]
            )

            state["retry_count"] = attempt

            print()
            print_line()
            print(
                "SQL ATTEMPT REJECTED - "
                "PREPARING RETRY"
            )
            print_line()

            print()
            print(
                "PREVIOUS SQL SAVED FOR RETRY:"
            )
            print(
                state["previous_sql"]
            )

            print()
            print(
                "CRITIQUE SAVED FOR RETRY:"
            )
            print(
                state["critique"]
            )

        # ----------------------------------------------------
        # Maximum attempts reached
        # ----------------------------------------------------

        else:

            print()
            print_line()
            print(
                "PIPELINE FAILED AFTER "
                "MAXIMUM ATTEMPTS"
            )
            print_line()

            print()
            print("LAST SQL:")
            print(
                state["sql"]
            )

            print()
            print(
                "LAST EXECUTION RESULT:"
            )
            print(
                state["query_result"]
            )

            print()
            print(
                "LAST EXECUTION ERROR:"
            )
            print(
                state["error"]
            )

            print()
            print(
                "FINAL CRITIQUE:"
            )
            print(
                state["critique"]
            )

            print()
            print(
                "RETRY COUNT:"
            )
            print(
                state["retry_count"]
            )

            raise AssertionError(
                "Retry test failed after maximum attempts."
            )


# ------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------

if __name__ == "__main__":
    main()