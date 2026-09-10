import json

from app.agent.state import AgentState
from app.llm.factory import get_llm_client
from app.core.error_types import ErrorType
from app.core.timing import measure_latency


# ============================================================
# CRITIC PROMPT
# ============================================================

CRITIC_PROMPT = """
You are a SQL critic for a PostgreSQL data-analyst agent.

Your job is to determine whether the generated SQL correctly answers
the user's question.

The RETRIEVED BUSINESS CONTEXT is the authoritative source for
business metric definitions.

The database schema determines which tables and columns exist.

Do NOT introduce business requirements that are not explicitly stated
in the retrieved business context.


============================================================
EXECUTION ERRORS
============================================================

If the SQL execution produced an error:

- valid MUST be false.
- Explain the actual execution error.
- Do not invent a different reason for rejection.

If the error is a timeout:

- valid MUST be false.
- Explain that the query failed to complete within the allowed time.
- Suggest improving efficiency only when appropriate.


============================================================
SUCCESSFUL EXECUTION
============================================================

A successful execution does NOT automatically mean the SQL is correct.

You must still verify that:

- the SQL follows the business definition
- the numerator is correct
- the denominator is correct
- filters do not incorrectly change the metric
- joins do not duplicate or remove entities
- aggregations match the intended metric


============================================================
EXACT SQL EXPRESSION VERIFICATION
============================================================

Before rejecting SQL, carefully inspect the ACTUAL SQL expressions.

Do not describe SQL from memory.

Do not assume that two expressions are equivalent without comparing
them exactly.

For example:

COUNT(DISTINCT session_id) FILTER (WHERE has_purchase)

is NOT the same expression as:

COUNT(DISTINCT session_id)

The FILTER condition changes the meaning of the aggregate.

You must carefully distinguish:

- filtered vs unfiltered aggregates
- COUNT(*) vs COUNT(column)
- COUNT(DISTINCT column) vs COUNT(column)
- CASE expressions vs non-CASE expressions
- WHERE conditions vs FILTER conditions
- numerator expressions vs denominator expressions

Before setting valid to false for a metric-definition problem:

1. Identify the exact SQL expression used for the numerator.
2. Identify the exact SQL expression used for the denominator.
3. Compare the numerator against the retrieved business definition.
4. Compare the denominator against the retrieved business definition.
5. Reject the SQL only if an expression actually violates the
   retrieved business definition.

Never claim that two SQL expressions are the same when their:

- filters
- conditions
- DISTINCT usage
- aggregation logic

are different.


============================================================
WHEN REJECTING SQL
============================================================

If valid is false, your feedback MUST explain:

1. The exact business rule that is violated.
2. The exact SQL expression causing the problem.
3. How the SQL should logically be corrected.

Do not give vague feedback.

Do not invent unrelated improvements.

Do not reject SQL based on assumptions or general knowledge that
conflicts with the retrieved business context.


============================================================
WHEN ACCEPTING SQL
============================================================

If:

- execution succeeded
- the SQL correctly implements the retrieved business definition
- the numerator is correct
- the denominator is correct
- no unsupported business conditions were introduced

then:

- valid MUST be true.
- feedback MUST be an empty string.


============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Use exactly this structure:

{
    "valid": true,
    "feedback": ""
}

or:

{
    "valid": false,
    "feedback": "Clear explanation of the exact problem."
}
"""


# ============================================================
# HELPER: PARSE JSON RESPONSE
# ============================================================

def parse_llm_response(response_text: str) -> dict:
    """
    Parse the critic LLM JSON response safely.

    Successful parsing returns:

        {
            "parsed": True,
            "data": {...}
        }

    Failed parsing returns:

        {
            "parsed": False,
            "error": "..."
        }

    Keeping parsing status separate from the actual critic response
    prevents malformed LLM output from being mistaken for a legitimate
    {"valid": false, ...} critic decision.
    """

    # --------------------------------------------------------
    # Empty response
    # --------------------------------------------------------

    if not response_text:
        return {
            "parsed": False,
            "error": "Critic returned an empty response."
        }

    response_text = response_text.strip()

    # --------------------------------------------------------
    # Remove markdown code fences
    # --------------------------------------------------------

    if response_text.startswith("```"):

        lines = response_text.splitlines()

        # Remove opening ```json or ```
        if lines:
            lines = lines[1:]

        # Remove closing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        response_text = "\n".join(lines).strip()

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:

        parsed = json.loads(response_text)

        return {
            "parsed": True,
            "data": parsed
        }

    except json.JSONDecodeError:

        return {
            "parsed": False,
            "error": (
                "Critic returned invalid JSON. "
                f"Raw response: {response_text}"
            )
        }


# ============================================================
# CRITIC NODE
# ============================================================

def critique_sql(state: AgentState) -> dict:
    """
    Review generated SQL using:

    - User question
    - Database schema
    - Retrieved business context
    - Generated SQL
    - Execution result
    - Execution error

    Latency tracking:

    - latencies["critic"] contains cumulative critic latency.
    - retry_latencies["attempt_X"]["critic"] contains critic latency
      for the specific attempt.
    """

    # --------------------------------------------------------
    # Extract state
    # --------------------------------------------------------

    question = state.get(
        "question",
        ""
    )

    schema = state.get(
        "schema",
        ""
    )

    retrieved_context = state.get(
        "retrieved_context",
        ""
    )

    sql = state.get(
        "sql",
        ""
    )

    query_result = state.get(
        "query_result",
        None
    )

    execution_error = state.get(
        "error",
        None
    )

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

    # --------------------------------------------------------
    # Current attempt
    #
    # 0 = initial attempt
    # 1 = first retry
    # 2 = second retry
    # --------------------------------------------------------

    attempt = state.get(
        "retry_count",
        0
    )

    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    if not sql:

        return {
            "sql_valid": False,
            "critique": "No SQL was generated.",
            "error_type": ErrorType.SQL_GENERATION_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # OBJECTIVE EXECUTION FAILURE CHECK
    #
    # If SQL execution failed, do not call the critic LLM.
    #
    # The executor has already classified the error.
    # We preserve that classification here.
    # --------------------------------------------------------

    if execution_error:

        return {
            "sql_valid": False,
            "critique": (
                f"SQL execution failed: {execution_error}"
            ),
            "error_type": state.get(
                "error_type",
                ErrorType.SQL_EXECUTION_ERROR.value
            ),
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Get LLM client
    # --------------------------------------------------------

    try:

        client = get_llm_client()

    except Exception as e:

        return {
            "sql_valid": False,
            "critique": (
                f"Critic LLM failed: {str(e)}"
            ),
            "error_type": ErrorType.CRITIC_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Build critic prompt
    # --------------------------------------------------------

    user_prompt = f"""
USER QUESTION:

{question}


============================================================
DATABASE SCHEMA
============================================================

{schema}


============================================================
RETRIEVED BUSINESS CONTEXT
============================================================

{retrieved_context}


============================================================
GENERATED SQL
============================================================

{sql}


============================================================
SQL EXECUTION RESULT
============================================================

{query_result}


============================================================
SQL EXECUTION ERROR
============================================================

{execution_error}


============================================================
YOUR TASK
============================================================

Review whether the SQL correctly answers the USER QUESTION.

The RETRIEVED BUSINESS CONTEXT is the authoritative source for the
metric definition.

Do not introduce requirements that are not explicitly stated in the
retrieved business context.

Check carefully:

1. Identify the exact SQL expression used for the numerator.
2. Identify the exact SQL expression used for the denominator.
3. Compare the numerator directly against the business definition.
4. Compare the denominator directly against the business definition.
5. Are filters correct?
6. Does the SQL accidentally exclude required entities?
7. Does the SQL introduce conditions not present in the business
   definition?
8. Did execution succeed?
9. If execution succeeded, does the SQL still implement the correct
   business logic?

IMPORTANT:

Do not reject SQL unless you can identify the exact SQL expression
that violates an explicit rule from the retrieved business context.

Do not claim that two SQL expressions are identical if one contains a:

- FILTER
- CASE
- WHERE condition
- DISTINCT modifier
- JOIN condition

that the other expression does not contain.

Compare the actual SQL expressions carefully.

If execution succeeded and the numerator and denominator correctly
match the retrieved business definition, valid MUST be true.

If rejecting the SQL, identify:

- the exact business rule violated
- the exact SQL expression causing the problem
- the logical correction required

Return ONLY JSON.
"""

    # --------------------------------------------------------
    # Call LLM
    # --------------------------------------------------------

    try:

        # ----------------------------------------------------
        # Measure cumulative + per-attempt critic latency
        # ----------------------------------------------------

        with measure_latency(
            latencies,
            "critic",
            attempt=attempt,
            retry_latencies=retry_latencies
        ):
            response = client.complete(
                CRITIC_PROMPT,
                [
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )

        response_text = response.content

        # ----------------------------------------------------
        # Debug output
        # ----------------------------------------------------

        print()
        print("RAW CRITIC RESPONSE:")
        print(response_text)

    except Exception as e:

        return {
            "sql_valid": False,
            "critique": (
                f"Critic LLM failed: {str(e)}"
            ),
            "error_type": ErrorType.CRITIC_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # ========================================================
    # PARSE RESPONSE
    # ========================================================

    parsed_result = parse_llm_response(
        response_text
    )

    # --------------------------------------------------------
    # Parsing failure
    # --------------------------------------------------------

    if not parsed_result.get(
        "parsed",
        False
    ):

        return {
            "sql_valid": False,
            "critique": parsed_result.get(
                "error",
                "Critic returned invalid JSON."
            ),
            "error_type": ErrorType.CRITIC_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Get parsed data
    # --------------------------------------------------------

    parsed = parsed_result.get(
        "data"
    )

    # --------------------------------------------------------
    # Validate returned structure
    # --------------------------------------------------------

    if not isinstance(
        parsed,
        dict
    ):

        return {
            "sql_valid": False,
            "critique": (
                "Critic returned an invalid response format."
            ),
            "error_type": ErrorType.CRITIC_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Required field validation
    #
    # A legitimate critic response MUST contain "valid".
    # --------------------------------------------------------

    if "valid" not in parsed:

        return {
            "sql_valid": False,
            "critique": (
                "Critic response is missing the required "
                "'valid' field."
            ),
            "error_type": ErrorType.CRITIC_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Validate "valid" type
    #
    # We expect the LLM to return a JSON boolean:
    #
    #     true
    #     false
    #
    # Do not silently accept arbitrary values.
    # --------------------------------------------------------

    if not isinstance(
        parsed["valid"],
        bool
    ):

        return {
            "sql_valid": False,
            "critique": (
                "Critic response contains an invalid "
                "'valid' field. Expected a boolean."
            ),
            "error_type": ErrorType.CRITIC_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Extract critic decision
    # --------------------------------------------------------

    valid = parsed[
        "valid"
    ]

    feedback = parsed.get(
        "feedback",
        ""
    )

    # --------------------------------------------------------
    # Normalize feedback
    # --------------------------------------------------------

    if feedback is None:
        feedback = ""

    feedback = str(
        feedback
    ).strip()

    # --------------------------------------------------------
    # Successful critic response
    # --------------------------------------------------------

    return {
        "sql_valid": valid,
        "critique": feedback,
        "error_type": ErrorType.NONE.value,
        "latencies": latencies,
        "retry_latencies": retry_latencies,
    }