import json
import re

from app.agent.state import AgentState
from app.llm.factory import get_llm_client
from app.core.error_types import ErrorType
from app.core.timing import measure_latency


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a PostgreSQL SQL generation assistant for TheLook e-commerce database.

Your job is to generate ONE correct, efficient, read-only PostgreSQL query
that answers the user's question.

You must follow this grounding priority:

1. Retrieved business context is the highest authority for business metric
   definitions.
2. Database schema determines which tables and columns exist.
3. Your SQL must correctly implement the business definition using the schema.

IMPORTANT RULES:

1. Use ONLY tables and columns provided in the database schema.
2. Never invent table names or column names.
3. Follow the retrieved business context exactly when it defines a metric.
4. Do not rely on assumptions that conflict with the business context.
5. Generate read-only SQL only.
6. Generate exactly one SQL statement.
7. Prefer efficient PostgreSQL queries.
8. When querying millions of rows, prefer simple aggregation over
   repeated row-by-row or session-by-session subqueries.
9. Avoid unnecessarily expensive correlated subqueries.
10. Avoid unnecessary CTEs and unnecessary GROUP BY operations.
11. Do not introduce requirements that are not present in the business context.


QUESTION INTENT / OUTPUT RULES:

1. Match the SQL output to exactly what the user asked for.

2. If the user asks:
   - "How many ..."
   - "How many sessions ..."
   - "How many events ..."
   - "What is the count ..."
   - "What is the number of ..."

   return ONLY the requested count.

3. Do NOT return additional numerator, denominator, percentage,
   intermediate values, or diagnostic columns unless the user explicitly
   asks for them.

4. If the question asks for the number of sessions satisfying a condition,
   return one COUNT(DISTINCT session_id) value with the appropriate filter.

5. Example:

   Question:
       How many sessions contain a purchase event?

   Correct:
       SELECT COUNT(DISTINCT session_id)
       FROM events
       WHERE event_type = 'purchase';

   Incorrect:
       SELECT
           COUNT(DISTINCT CASE
               WHEN event_type = 'purchase' THEN session_id
           END) AS numerator,
           COUNT(DISTINCT session_id) AS denominator
       FROM events;

6. A ratio/percentage question is different from a count question.

   For example:

       "What is the conversion rate?"

   requires both numerator and denominator.

   But:

       "How many sessions contain a purchase event?"

   requires only the requested count.


SESSION-LEVEL METRIC RULES:

When a metric is defined in terms of DISTINCT sessions:

1. Preserve the exact numerator and denominator from the business definition.

2. If the metric is:

       sessions satisfying condition / all sessions

   prefer conditional aggregation:

       COUNT(DISTINCT CASE
           WHEN <condition> THEN session_id
       END)
       /
       COUNT(DISTINCT session_id)

   or PostgreSQL FILTER syntax when appropriate:

       COUNT(DISTINCT session_id)
       FILTER (WHERE <condition>)
       /
       COUNT(DISTINCT session_id)

3. Do NOT use a correlated EXISTS subquery to determine whether a session
   satisfies a condition when conditional aggregation can express the same
   logic.

4. Do NOT use CROSS JOIN or comma joins between large DISTINCT session
   result sets to calculate a scalar ratio.

5. Do NOT use UNION or UNION ALL to calculate the numerator and denominator
   of a single metric.

6. Do NOT use NOT IN against the large events table when conditional
   aggregation can express the required logic.

7. Do NOT add filters to the denominator unless the business definition
   explicitly requires those filters.

8. For a definition such as:

       purchase sessions / all sessions

   the numerator is:

       sessions with at least one purchase

   and the denominator is:

       all distinct sessions

   The denominator must NOT be restricted to cart or purchase events unless
   the business definition explicitly says so.

9. A query that executes successfully is NOT necessarily correct.
   Preserve the exact business meaning of the metric.

10. Prefer a single scan and conditional aggregation when it correctly
    expresses the metric.


IMPORTANT METRIC EXAMPLE:

If the business definition says:

    purchase sessions / all sessions

then:

    Numerator   = distinct sessions with at least one purchase
    Denominator = all distinct sessions

A preferred implementation is conceptually:

    COUNT(DISTINCT CASE
        WHEN event_type = 'purchase' THEN session_id
    END)
    * 100.0
    / COUNT(DISTINCT session_id)

Do not add cart events.
Do not use a correlated EXISTS.
Do not use a CROSS JOIN between large session sets.
Do not use UNION ALL.
Do not change the denominator.


RETRY RULES:

If critic feedback is provided, this is a RETRY.

The previous SQL attempt was rejected.

You must:

1. Identify the actual problem with the previous SQL.
2. Address the execution error or valid critic feedback.
3. Follow the retrieved business definition exactly.
4. Preserve the exact numerator and denominator when the metric requires them.
5. Do not introduce new business requirements.
6. If the previous query timed out, simplify the query rather than merely
   rewriting the same expensive pattern.
7. If the critic identifies a correlated subquery, do not use another
   correlated subquery as the replacement.
8. If the critic identifies an incorrect numerator, explicitly rebuild the
   numerator from the business definition.
9. If the critic identifies an incorrect denominator, explicitly rebuild the
   denominator from the business definition.
10. Do not blindly trust critic feedback if it conflicts with the retrieved
    business context.
11. Generate a materially corrected query.
12. Prefer simple conditional aggregation for session-level ratios when
    applicable.
13. If the original question is a count question, return ONLY the requested
    count even during a retry.


ANTI-PATTERN CHECK BEFORE RETURNING SQL:

Before generating the final SQL, mentally verify:

- Does the SQL answer exactly what the user asked?
- If this is a count question, am I returning only the requested count?
- If this is a ratio/percentage question, are the numerator and denominator
  both required and correct?
- Am I using a correlated EXISTS unnecessarily?
- Am I creating a CROSS JOIN or Cartesian product?
- Am I using UNION/UNION ALL for one scalar metric?
- Am I using NOT IN against the large events table unnecessarily?
- Did I accidentally filter the denominator?
- Does the numerator exactly match the business definition?
- Does the denominator exactly match the business definition?
- Can conditional aggregation express this more simply?

If any answer indicates an unnecessary expensive or semantically incorrect
pattern, rewrite the query before returning it.

Respond ONLY with valid JSON in this format:

{"sql": "SELECT ..."}
"""


# ============================================================
# PARSE SQL RESPONSE
# ============================================================

def parse_sql(text: str) -> str | None:
    """
    Extract SQL from the LLM response.

    Expected format:

    {"sql": "SELECT ..."}
    """

    if not text:
        return None

    text = text.strip()

    # --------------------------------------------------------
    # First try parsing the complete response as JSON
    # --------------------------------------------------------

    try:
        data = json.loads(text)

        sql = data.get("sql")

        if isinstance(sql, str) and sql.strip():
            return sql.strip()

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Try extracting JSON from the response
    # --------------------------------------------------------

    match = re.search(
        r'\{[\s\S]*?"sql"\s*:\s*"([\s\S]*?)"[\s\S]*?\}',
        text
    )

    if match:
        try:
            json_match = match.group(0)

            data = json.loads(json_match)

            sql = data.get("sql")

            if isinstance(sql, str) and sql.strip():
                return sql.strip()

        except Exception:
            pass

    # --------------------------------------------------------
    # Try SQL inside markdown code block
    # --------------------------------------------------------

    match = re.search(
        r"```(?:sql)?\s*([\s\S]*?)```",
        text,
        re.IGNORECASE
    )

    if match:
        sql = match.group(1).strip()

        if sql:
            return sql

    return None


# ============================================================
# GENERATE SQL
# ============================================================

def generate_sql(state: AgentState) -> dict:
    """
    Generate grounded SQL.

    First attempt:
        Uses question + schema + business context.

    Retry:
        Uses question + schema + business context
        + previous SQL + critic feedback.

    Latency:
        - cumulative SQL-generation latency
        - per-attempt SQL-generation latency
    """

    # --------------------------------------------------------
    # State values
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

    previous_sql = state.get(
        "previous_sql"
    )

    critique = state.get(
        "critique"
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
    # Get LLM client
    # --------------------------------------------------------

    try:
        client = get_llm_client()

    except Exception as e:

        return {
            "sql": None,
            "error": (
                f"SQL generation failed: {str(e)}"
            ),
            "error_type": ErrorType.LLM_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # ========================================================
    # FIRST ATTEMPT
    # ========================================================

    if not previous_sql:

        user_prompt = f"""
QUESTION:
{question}


DATABASE SCHEMA:
{schema}


RETRIEVED BUSINESS CONTEXT:
{retrieved_context}


Generate the correct PostgreSQL SQL query.

Remember:

- Business context has priority for metric definitions.
- Match the SQL output to exactly what the question asks.
- If the question asks "how many" or asks for a count, return only that count.
- Do not return numerator/denominator pairs unless the question asks for a
  ratio, percentage, or both values.
- For "How many sessions contain a purchase event?", return only
  COUNT(DISTINCT session_id) for purchase sessions.
- Use only tables and columns from the schema.
- Do not invent business requirements.
- Use all entities required by the metric definition.
- Do not add filters that incorrectly change a denominator.
- Prefer efficient SQL for large tables.
- Avoid unnecessary CTEs, GROUP BY operations, and expensive patterns.
- For session-level metrics, preserve the exact numerator and denominator
  when the metric actually requires both.
- Avoid correlated EXISTS when conditional aggregation can express the logic.
- Avoid CROSS JOIN or Cartesian products between large session sets.
- Avoid UNION or UNION ALL for a single scalar metric.
- Avoid unnecessary NOT IN subqueries over the events table.
- Generate exactly one read-only SQL statement.

Before returning the SQL, verify:

1. Does the SQL answer exactly what the user asked?
2. If this is a count question, does the SQL return only the requested count?
3. If this is a ratio/percentage question, are both numerator and denominator
   correct?
4. The numerator matches the business definition when a numerator is required.
5. The denominator matches the business definition when a denominator is required.
6. No unnecessary filters were added to the denominator.
7. No unnecessary correlated subquery is being used.
8. No Cartesian product is being created.
9. The query is as simple as possible while remaining correct.

Respond ONLY with JSON:

{{"sql": "SELECT ..."}}
"""

    # ========================================================
    # RETRY ATTEMPT
    # ========================================================

    else:

        user_prompt = f"""
QUESTION:
{question}


DATABASE SCHEMA:
{schema}


RETRIEVED BUSINESS CONTEXT:
{retrieved_context}


============================================================
PREVIOUS SQL ATTEMPT
============================================================

{previous_sql}


============================================================
CRITIC / EXECUTION FEEDBACK
============================================================

{critique}


============================================================
RETRY INSTRUCTIONS
============================================================

The previous SQL was rejected.

You MUST generate a corrected query.

However, follow these rules carefully:

1. The retrieved business context is the highest authority for the metric
   definition.

2. Fix the actual problem in the previous SQL.

3. Match the SQL output to exactly what the original question asks.

4. If the original question asks "how many", "what is the count", or asks
   for the number of something, return ONLY the requested count.

5. Do NOT return additional numerator, denominator, percentage, intermediate
   values, or diagnostic columns unless the original question explicitly
   asks for them.

6. If the question asks for a ratio or percentage, calculate the complete
   ratio using the required numerator and denominator.

7. If the feedback reports an execution error or timeout, generate a more
   efficient query.

8. Do NOT introduce requirements that are not explicitly stated in the
   retrieved business context.

9. Do NOT blindly follow feedback that conflicts with the business context.

10. Do not change the meaning of the metric.

11. Preserve the exact numerator and denominator when the metric requires
    both.

12. If the previous SQL used a correlated EXISTS unnecessarily, replace it
    with a simpler set-based or conditional aggregation approach.

13. If the previous SQL used CROSS JOIN, comma joins between large result
    sets, UNION/UNION ALL, or NOT IN unnecessarily, do not repeat that
    pattern.

14. If the previous SQL has an incorrect numerator, rebuild the numerator
    directly from the business definition.

15. If the previous SQL has an incorrect denominator, rebuild the denominator
    directly from the business definition.

16. Do not add filters to the denominator unless explicitly required.

17. Prefer simple conditional aggregation for session-level ratios when
    applicable.

18. Prefer a single scan over the events table when it correctly expresses
    the requested metric.

19. Generate a materially corrected query rather than making superficial
    changes to the previous SQL.


IMPORTANT COUNT EXAMPLE:

Question:

    How many sessions contain a purchase event?

Correct:

    SELECT COUNT(DISTINCT session_id)
    FROM events
    WHERE event_type = 'purchase';

Incorrect:

    SELECT
        COUNT(DISTINCT CASE
            WHEN event_type = 'purchase' THEN session_id
        END) AS numerator,
        COUNT(DISTINCT session_id) AS denominator
    FROM events;


IMPORTANT RATIO EXAMPLE:

If the business definition is:

    purchase sessions / all sessions

then:

    Numerator   = distinct sessions with at least one purchase
    Denominator = all distinct sessions

A preferred implementation is:

    COUNT(DISTINCT CASE
        WHEN event_type = 'purchase' THEN session_id
    END)
    * 100.0
    / COUNT(DISTINCT session_id)

Do NOT:

- use correlated EXISTS
- use CROSS JOIN between large session sets
- use UNION ALL
- use NOT IN against the events table
- restrict the denominator to cart/purchase events
- change the metric definition


Before returning the SQL, verify:

1. Does the query answer exactly what the original question asks?
2. If it is a count question, does it return exactly one requested count?
3. If it is a ratio/percentage question, are both numerator and denominator
   correct?
4. Are both based on the retrieved business definition?
5. Did I accidentally filter the denominator?
6. Is there a correlated subquery that can be removed?
7. Is there a Cartesian product?
8. Is there unnecessary UNION/UNION ALL?
9. Can conditional aggregation solve this more efficiently?

Generate the corrected PostgreSQL SQL now.

Respond ONLY with JSON:

{{"sql": "SELECT ..."}}
"""

    # ========================================================
    # CALL LLM
    # ========================================================

    try:

        # ----------------------------------------------------
        # Measure both cumulative and per-attempt latency
        # ----------------------------------------------------

        with measure_latency(
            latencies,
            "sql_generation",
            attempt=attempt,
            retry_latencies=retry_latencies
        ):
            response = client.complete(
                SYSTEM_PROMPT,
                [
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )

        # ----------------------------------------------------
        # Debug output
        # ----------------------------------------------------

        print()
        print("RAW LLM RESPONSE:")
        print(response.content)

        # ----------------------------------------------------
        # Parse SQL
        # ----------------------------------------------------

        sql = parse_sql(
            response.content
        )

        # ----------------------------------------------------
        # SQL parsing failure
        # ----------------------------------------------------

        if sql is None:

            return {
                "sql": None,
                "error": (
                    "Could not parse SQL from LLM response."
                ),
                "error_type": (
                    ErrorType.SQL_GENERATION_ERROR.value
                ),
                "latencies": latencies,
                "retry_latencies": retry_latencies,
            }

        # ----------------------------------------------------
        # Successful SQL generation
        # ----------------------------------------------------

        return {
            "sql": sql,
            "error": None,
            "error_type": ErrorType.NONE.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # LLM failure
    # --------------------------------------------------------

    except Exception as e:

        return {
            "sql": None,
            "error": (
                f"SQL generation failed: {str(e)}"
            ),
            "error_type": ErrorType.LLM_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }