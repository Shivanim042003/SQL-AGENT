import sys
from pathlib import Path
import json
import re

import psycopg2

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

import config

from app.llm.factory import get_llm_client
from app.execution.schema_info import get_schema_summary
from app.retrieval.factory import get_embedding_client
from app.retrieval.retriever import Retriever


QUESTION = "What is the conversion rate?"


NO_GROUNDING_PROMPT = """
You are a SQL generation assistant for a PostgreSQL e-commerce database.

Generate SQL to answer the user's question.

Respond with ONLY a JSON object in this format:

{"sql": "SELECT ..."}
"""


SCHEMA_GROUNDING_PROMPT = """
You are a SQL generation assistant for a PostgreSQL e-commerce database.

Use ONLY the exact table names and column names provided in the schema.

Never invent:
- tables
- columns
- event types
- status values

SCHEMA:
{schema}

Generate SQL to answer the user's question.

Respond with ONLY a JSON object in this format:

{{"sql": "SELECT ..."}}
"""


RETRIEVAL_GROUNDING_PROMPT = """
You are a SQL generation assistant for a PostgreSQL e-commerce database.

Use ONLY the exact table names and column names provided in the schema.

Never invent:
- tables
- columns
- event types
- status values

Use the retrieved business context to determine the correct business definition.

SCHEMA:
{schema}

RETRIEVED BUSINESS CONTEXT:
{context}

Generate SQL that answers the user's question according to the retrieved
business definition.

Respond with ONLY a JSON object in this format:

{{"sql": "SELECT ..."}}
"""


def parse_sql(text: str) -> str | None:
    """Extract SQL from the LLM JSON response."""

    text = text.strip()

    try:
        data = json.loads(text)
        return data.get("sql")

    except json.JSONDecodeError:

        match = re.search(r"\{.*\}", text, re.DOTALL)

        if match:
            try:
                data = json.loads(match.group(0))
                return data.get("sql")

            except json.JSONDecodeError:
                pass

    return None


def run_sql(sql: str):
    """Execute SQL and return either the result or an error."""

    conn = None
    cur = None

    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        cur = conn.cursor()

        cur.execute(sql)

        result = cur.fetchall()

        return result, None

    except Exception as e:
        return None, str(e)

    finally:
        if cur is not None:
            cur.close()

        if conn is not None:
            conn.close()


def print_execution(sql: str | None):
    """Print SQL and execute it if available."""

    print("\nPARSED SQL:")

    if sql is None:
        print("Could not parse SQL from response.")
        return

    print(sql)

    result, error = run_sql(sql)

    print("\nEXECUTION RESULT:")

    if error:
        print(f"ERROR: {error}")
    else:
        print(result)


def format_retrieved_context(results: list[dict]) -> str:
    """Convert retrieval results into context for the LLM."""

    sections = []

    for i, result in enumerate(results, start=1):

        section = f"""
RESULT {i}

SOURCE:
{result["source"]}

CONTENT:
{result["content"]}
"""

        sections.append(section.strip())

    return "\n\n".join(sections)


def main():

    # ------------------------------------------------------------
    # Initialize clients
    # ------------------------------------------------------------

    llm_client = get_llm_client()

    embedding_client = get_embedding_client()

    retriever = Retriever(embedding_client)

    # ------------------------------------------------------------
    # TEST A — No grounding
    # ------------------------------------------------------------

    print("=" * 80)
    print("TEST A — NO GROUNDING")
    print("=" * 80)

    response_a = llm_client.complete(
        NO_GROUNDING_PROMPT,
        [
            {
                "role": "user",
                "content": QUESTION
            }
        ]
    )

    print("\nRAW RESPONSE:")
    print(response_a.content)

    sql_a = parse_sql(response_a.content)

    print_execution(sql_a)

    # ------------------------------------------------------------
    # TEST B — Schema grounding
    # ------------------------------------------------------------

    print("\n" + "=" * 80)
    print("TEST B — SCHEMA GROUNDING")
    print("=" * 80)

    schema = get_schema_summary()

    response_b = llm_client.complete(
        SCHEMA_GROUNDING_PROMPT.format(
            schema=schema
        ),
        [
            {
                "role": "user",
                "content": QUESTION
            }
        ]
    )

    print("\nRAW RESPONSE:")
    print(response_b.content)

    sql_b = parse_sql(response_b.content)

    print_execution(sql_b)

    # ------------------------------------------------------------
    # TEST C — Schema + Retrieval grounding
    # ------------------------------------------------------------

    print("\n" + "=" * 80)
    print("TEST C — SCHEMA + RETRIEVAL GROUNDING")
    print("=" * 80)

    results = retriever.search(
        QUESTION,
        top_k=1
    )

    retrieved_context = format_retrieved_context(results)

    print("\nRETRIEVED CONTEXT:")
    print(retrieved_context)

    response_c = llm_client.complete(
        RETRIEVAL_GROUNDING_PROMPT.format(
            schema=schema,
            context=retrieved_context
        ),
        [
            {
                "role": "user",
                "content": QUESTION
            }
        ]
    )

    print("\nRAW RESPONSE:")
    print(response_c.content)

    sql_c = parse_sql(response_c.content)

    print_execution(sql_c)


if __name__ == "__main__":
    main()