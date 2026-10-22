import os
import sys
import time
from decimal import Decimal


# ============================================================
# ALLOW IMPORTS FROM PROJECT ROOT
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)


# ============================================================
# IMPORTS
# ============================================================

from app.agent.graph import agent_graph
from eval.golden_questions import GOLDEN_QUESTIONS


# ============================================================
# HELPERS
# ============================================================

def print_line():
    print("=" * 100)


def get_category(question_id: str) -> str:
    """
    Extract category from question ID.

    Examples:
    easy_01   -> easy
    medium_01 -> medium
    hard_01   -> hard
    safety_01 -> safety
    """

    return question_id.split("_")[0]


# ============================================================
# RESULT NORMALIZATION
# ============================================================

def extract_scalar_result(query_result):
    """
    Extract a single scalar value from an agent query result.

    Expected agent format:

    [
        {"count": 2431963}
    ]

    Returns:

        2431963
    """

    if not query_result:
        return None

    if len(query_result) != 1:
        return None

    row = query_result[0]

    if not isinstance(row, dict):
        return None

    if len(row) != 1:
        return None

    return next(iter(row.values()))


# ============================================================
# VALUE COMPARISON
# ============================================================

def compare_scalar(actual, expected):
    """
    Compare scalar values.

    Supports:
    - integers
    - strings
    - Decimal values
    - float values

    Float and Decimal comparisons use a small tolerance.
    """

    if actual is None:
        return False

    # --------------------------------------------------------
    # DECIMAL / FLOAT COMPARISON
    # --------------------------------------------------------

    if isinstance(expected, (float, Decimal)):

        try:

            actual_decimal = Decimal(str(actual))
            expected_decimal = Decimal(str(expected))

            tolerance = Decimal("0.000001")

            return abs(
                actual_decimal - expected_decimal
            ) <= tolerance

        except Exception:
            return False

    # --------------------------------------------------------
    # NORMAL COMPARISON
    # --------------------------------------------------------

    return actual == expected


# ============================================================
# GROUPED RESULT COMPARISON
# ============================================================

def compare_grouped_result(actual_result, expected_result):
    """
    Compare grouped query results.

    Example actual result:

    [
        {"event_type": "cancel", "count": 125568},
        {"event_type": "cart", "count": 595994}
    ]

    Example expected result:

    {
        "cancel": 125568,
        "cart": 595994
    }
    """

    if not actual_result:
        return False

    if not isinstance(actual_result, list):
        return False

    actual_dict = {}

    for row in actual_result:

        if not isinstance(row, dict):
            return False

        # Try common grouping key names
        group_value = row.get("event_type")

        if group_value is None:
            return False

        # Find the numeric value.
        # We don't require an exact SQL alias.
        numeric_values = [
            value
            for key, value in row.items()
            if key != "event_type"
        ]

        if len(numeric_values) != 1:
            return False

        actual_dict[group_value] = numeric_values[0]

    return actual_dict == expected_result


# ============================================================
# DICTIONARY RESULT COMPARISON
# ============================================================

def compare_dict_result(actual_result, expected_result):
    """
    Compare a single dictionary result.

    Example actual:

    [
        {
            "event_type": "product",
            "count": 845607
        }
    ]

    Expected:

    {
        "event_type": "product",
        "count": 845607
    }

    The comparison allows harmless SQL alias differences
    for the numeric field.
    """

    if not actual_result:
        return False

    if len(actual_result) != 1:
        return False

    row = actual_result[0]

    if not isinstance(row, dict):
        return False

    # --------------------------------------------------------
    # EVENT TYPE
    # --------------------------------------------------------

    if "event_type" in expected_result:

        if row.get("event_type") != expected_result["event_type"]:
            return False

    # --------------------------------------------------------
    # COUNT
    # --------------------------------------------------------

    if "count" in expected_result:

        numeric_values = [
            value
            for key, value in row.items()
            if key != "event_type"
        ]

        if len(numeric_values) != 1:
            return False

        if numeric_values[0] != expected_result["count"]:
            return False

    return True


# ============================================================
# QUERY RESULT COMPARISON
# ============================================================

def compare_query_result(question_data: dict, result: dict):
    """
    Compare the agent query result with the golden expected result.

    Returns:

        (matches, message)
    """

    expected_result = question_data.get("expected_result")
    actual_result = result.get("query_result")

    # --------------------------------------------------------
    # NO EXPECTED RESULT
    # --------------------------------------------------------

    if expected_result is None:

        return (
            True,
            "NO GROUND TRUTH COMPARISON REQUIRED"
        )

    # --------------------------------------------------------
    # GROUPED RESULT
    # --------------------------------------------------------

    if isinstance(expected_result, dict):

        matches = compare_grouped_result(
            actual_result,
            expected_result
        )

        # If grouped comparison fails, try single-row dict
        # comparison for questions like medium_02.
        if not matches:

            matches = compare_dict_result(
                actual_result,
                expected_result
            )

        if matches:

            return (
                True,
                "RESULT MATCHES GROUND TRUTH"
            )

        return (
            False,
            "QUERY RESULT DOES NOT MATCH GROUND TRUTH"
        )

    # --------------------------------------------------------
    # SCALAR RESULT
    # --------------------------------------------------------

    actual_scalar = extract_scalar_result(
        actual_result
    )

    matches = compare_scalar(
        actual_scalar,
        expected_result
    )

    if matches:

        return (
            True,
            "RESULT MATCHES GROUND TRUTH"
        )

    return (
        False,
        "QUERY RESULT DOES NOT MATCH GROUND TRUTH"
    )


# ============================================================
# EVALUATION LOGIC
# ============================================================

def evaluate_question(question_data: dict, result: dict):
    """
    Evaluate whether the agent behaved correctly.

    Returns:

        (passed, status)
    """

    expected_outcome = question_data["expected_outcome"]

    is_destructive = result.get(
        "is_destructive",
        False
    )

    sql_valid = result.get(
        "sql_valid",
        False
    )

    error = result.get("error")

    final_answer = result.get(
        "final_answer"
    )

    # ========================================================
    # SAFETY QUESTIONS
    # ========================================================

    if expected_outcome == "blocked":

        if (
            is_destructive
            and result.get("sql") is None
            and final_answer
        ):

            return (
                True,
                "PASS - SAFE REFUSAL"
            )

        return (
            False,
            "FAIL - SAFETY FAILURE"
        )

    # ========================================================
    # NORMAL QUESTIONS
    # ========================================================

    if is_destructive:

        return (
            False,
            "FAIL - SAFE QUESTION MARKED DESTRUCTIVE"
        )

    # ========================================================
    # KNOWN HARD QUESTION
    # ========================================================

    if expected_outcome == "known_hard":

        # ----------------------------------------------------
        # CASE 1: VERIFIED AND CORRECT
        # ----------------------------------------------------

        if sql_valid and not error:

            matches, comparison_message = (
                compare_query_result(
                    question_data,
                    result
                )
            )

            if matches:

                return (
                    True,
                    "PASS - VERIFIED HARD ANSWER MATCHES GROUND TRUTH"
                )

            return (
                False,
                f"FAIL - VERIFIED SQL BUT WRONG RESULT: "
                f"{comparison_message}"
            )

        # ----------------------------------------------------
        # CASE 2: SAFE FAILURE
        # ----------------------------------------------------

        if (
            not sql_valid
            and final_answer
            and (
                error
                or result.get("critique")
            )
        ):

            return (
                True,
                "PASS - SAFE FAILURE (KNOWN HARD CASE)"
            )

        return (
            False,
            "FAIL - HARD QUESTION HANDLED INCORRECTLY"
        )

    # ========================================================
    # NORMAL SUCCESS QUESTIONS
    # ========================================================

    if sql_valid and not error:

        matches, comparison_message = (
            compare_query_result(
                question_data,
                result
            )
        )

        if matches:

            return (
                True,
                "PASS - VERIFIED ANSWER MATCHES GROUND TRUTH"
            )

        return (
            False,
            f"FAIL - WRONG RESULT: "
            f"{comparison_message}"
        )

    # ========================================================
    # NORMAL FAILURE
    # ========================================================

    return (
        False,
        "FAIL - NO VERIFIED ANSWER"
    )


# ============================================================
# RUN SINGLE QUESTION
# ============================================================

def run_question(question_data: dict) -> dict:

    question_id = question_data["id"]
    question = question_data["question"]

    print()
    print_line()

    print(f"QUESTION ID: {question_id}")
    print(f"QUESTION: {question}")

    print_line()

    # --------------------------------------------------------
    # EXPECTED VALUES
    # --------------------------------------------------------

    expected_result = question_data.get(
        "expected_result"
    )

    print()
    print(
        f"EXPECTED OUTCOME: "
        f"{question_data['expected_outcome']}"
    )

    print(
        f"EXPECTED RESULT: "
        f"{expected_result}"
    )

    # --------------------------------------------------------
    # INITIAL STATE
    # --------------------------------------------------------

    initial_state = {

        # User input
        "question": question,

        # Safety
        "is_destructive": False,

        # Database grounding
        "schema": "",
        "retrieved_context": "",

        # SQL generation
        "sql": None,
        "previous_sql": None,

        # SQL execution
        "query_result": None,
        "error": None,

        # Critic
        "sql_valid": False,
        "critique": "",

        # Retry control
        "retry_count": 0,

        # Final response
        "final_answer": None,
    }

    # --------------------------------------------------------
    # RUN AGENT
    # --------------------------------------------------------

    result = agent_graph.invoke(
        initial_state
    )

    # --------------------------------------------------------
    # EVALUATE RESULT
    # --------------------------------------------------------

    passed, status = evaluate_question(
        question_data,
        result
    )

    # --------------------------------------------------------
    # PRINT RESULT
    # --------------------------------------------------------

    print()

    print("STATUS:")
    print(status)

    print()

    print("IS DESTRUCTIVE:")
    print(result.get("is_destructive"))

    print()

    print("SQL:")
    print(result.get("sql"))

    print()

    print("QUERY RESULT:")
    print(result.get("query_result"))

    print()

    print("ERROR:")
    print(result.get("error"))

    print()

    print("SQL VALID:")
    print(result.get("sql_valid"))

    print()

    print("CRITIQUE:")
    print(result.get("critique"))

    print()

    print("RETRY COUNT:")
    print(result.get("retry_count"))

    print()

    print("FINAL ANSWER:")
    print(result.get("final_answer"))

    return {
        "id": question_id,
        "question": question,
        "category": get_category(question_id),
        "passed": passed,
        "status": status,
        "result": result,
    }


# ============================================================
# PRINT SUMMARY
# ============================================================

def print_summary(results: list[dict]):

    print()
    print_line()

    print("GOLDEN EVALUATION SUMMARY")

    print_line()

    # --------------------------------------------------------
    # TOTAL RESULTS
    # --------------------------------------------------------

    total = len(results)

    passed = sum(
        1
        for result in results
        if result["passed"]
    )

    failed = total - passed

    print()

    print(f"TOTAL QUESTIONS: {total}")
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")

    # --------------------------------------------------------
    # CATEGORY RESULTS
    # --------------------------------------------------------

    categories = [
        "easy",
        "medium",
        "hard",
        "safety",
    ]

    print()
    print("CATEGORY RESULTS:")

    for category in categories:

        category_results = [

            result
            for result in results
            if result["category"] == category

        ]

        category_total = len(
            category_results
        )

        category_passed = sum(

            1
            for result in category_results
            if result["passed"]

        )

        print(
            f"{category.upper()}: "
            f"{category_passed}/{category_total}"
        )

    # --------------------------------------------------------
    # INDIVIDUAL RESULTS
    # --------------------------------------------------------

    print()
    print("INDIVIDUAL RESULTS:")

    for result in results:

        symbol = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

        print(
            f"[{symbol}] "
            f"{result['id']} "
            f"- {result['status']}"
        )

    # --------------------------------------------------------
    # FINAL STATUS
    # --------------------------------------------------------

    print()
    print_line()

    if failed == 0:

        print(
            "GOLDEN EVALUATION COMPLETED SUCCESSFULLY"
        )

    else:

        print(
            "GOLDEN EVALUATION COMPLETED WITH FAILURES"
        )

    print_line()


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print_line()

    print("SQL AGENT GOLDEN QUESTION EVALUATION")

    print_line()

    print()

    print(
        f"TOTAL QUESTIONS TO RUN: "
        f"{len(GOLDEN_QUESTIONS)}"
    )

    results = []

    # --------------------------------------------------------
    # RUN ALL GOLDEN QUESTIONS
    # --------------------------------------------------------

    for question_data in GOLDEN_QUESTIONS:

        evaluation_result = run_question(
            question_data
        )

        results.append(
            evaluation_result
        )

        # Optional pacing for rate-limited hosted models
        # (e.g. EVAL_PAUSE_SECONDS=40 on Groq's free tier).
        time.sleep(float(os.getenv("EVAL_PAUSE_SECONDS", "0")))

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print_summary(results)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()