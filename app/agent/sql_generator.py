import json
import re

from app.agent.state import AgentState
from app.llm.factory import get_llm_client


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
8. Avoid unnecessarily expensive correlated subqueries on large tables.
9. Avoid unnecessary CTEs and unnecessary GROUP BY operations.
10. When calculating metrics over millions of rows, prefer efficient
    aggregations and indexed columns where possible.
11. Do not introduce requirements that are not present in the business context.
12. Respond ONLY with valid JSON in this format:

{"sql": "SELECT ..."}

RETRY RULES:

If critic feedback is provided, this is a RETRY.

The previous SQL attempt was rejected.

You must:

- Identify the actual problem with the previous SQL.
- Address the execution error or valid critic feedback.
- Follow the retrieved business definition exactly.
- Do not introduce new requirements not present in the business context.
- Prefer a simpler and more efficient query when the previous query timed out.
- Do not blindly trust critic feedback if it conflicts with the retrieved
  business context.
- Generate a materially corrected query.

IMPORTANT METRIC EXAMPLE:

If the business definition says:

purchase sessions / all sessions

then:

- Numerator = sessions with at least one purchase.
- Denominator = all sessions.
- Do NOT add unrelated requirements such as cart events unless explicitly
  required by the business context.

Always prioritize the retrieved business context.
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
    """

    # --------------------------------------------------------
    # Get state values
    # --------------------------------------------------------

    question = state.get("question", "")

    schema = state.get("schema", "")

    retrieved_context = state.get("retrieved_context", "")

    previous_sql = state.get("previous_sql")

    critique = state.get("critique")

    # --------------------------------------------------------
    # Get LLM client
    # --------------------------------------------------------

    client = get_llm_client()

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
- Use only tables and columns from the schema.
- Do not invent business requirements.
- Use all entities required by the metric definition.
- Do not add filters that incorrectly change a denominator.
- Prefer efficient SQL for large tables.
- Avoid unnecessary CTEs, GROUP BY operations, and expensive patterns.
- Generate exactly one read-only SQL statement.

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

3. If the feedback reports an execution error or timeout, generate a more
   efficient query.

4. Do NOT introduce requirements that are not explicitly stated in the
   retrieved business context.

5. Do NOT blindly follow feedback that conflicts with the business context.

6. Do not change the meaning of the metric.

7. Preserve the correct numerator and denominator defined by the business
   context.

8. Prefer simpler and more efficient SQL.

9. Avoid unnecessarily expensive CTEs and GROUP BY operations.

10. Generate exactly one read-only PostgreSQL statement.

IMPORTANT:

The critic feedback is useful for identifying problems, but the retrieved
business context remains the highest authority.

Generate the corrected PostgreSQL SQL now.

Respond ONLY with JSON:

{{"sql": "SELECT ..."}}
"""

    # ========================================================
    # CALL LLM
    # ========================================================

    try:

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

        sql = parse_sql(response.content)

        if sql is None:

            return {
                "sql": None,
                "error": "Could not parse SQL from LLM response."
            }

        return {
            "sql": sql,
            "error": None
        }

    except Exception as e:

        return {
            "sql": None,
            "error": f"SQL generation failed: {str(e)}"
        }