import json
import re

from app.agent.state import AgentState
from app.llm.factory import get_llm_client


SYSTEM_PROMPT = """
You are a PostgreSQL SQL generation assistant for TheLook e-commerce database.

Generate SQL that answers the user's question.

IMPORTANT RULES:

1. Use ONLY the tables and columns provided in the database schema.
2. Never invent table names or column names.
3. Use the retrieved business context when it defines how a metric should be calculated.
4. If the business context conflicts with your assumptions, follow the business context.
5. Generate read-only SQL only.
6. Only generate a single SQL SELECT statement.
7. Respond ONLY with valid JSON in this format:

{"sql": "SELECT ..."}
"""


def parse_sql(text: str) -> str | None:
    """Extract SQL from the LLM JSON response."""

    text = text.strip()

    try:
        data = json.loads(text)
        return data.get("sql")

    except json.JSONDecodeError:

        # Try extracting a JSON object if the model adds extra text
        match = re.search(r"\{.*\}", text, re.DOTALL)

        if match:
            try:
                data = json.loads(match.group(0))
                return data.get("sql")

            except json.JSONDecodeError:
                pass

    return None


def generate_sql(state: AgentState) -> dict:
    """Generate grounded SQL from the question, schema, and retrieved context."""

    client = get_llm_client()

    user_prompt = f"""
USER QUESTION:

{state["question"]}


DATABASE SCHEMA:

{state["schema"]}


RETRIEVED BUSINESS CONTEXT:

{state["retrieved_context"]}
"""

    response = client.complete(
        SYSTEM_PROMPT,
        [
            {
                "role": "user",
                "content": user_prompt
            }
        ]
    )

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