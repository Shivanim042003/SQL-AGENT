import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

import json
import re

import psycopg2

import config

from app.llm.factory import get_llm_client
from app.execution.schema_info import get_schema_summary


QUESTION = "What is the average cost per inventory item?"


NO_SCHEMA_PROMPT = """
You are a SQL generation assistant for a PostgreSQL e-commerce database.

Respond with ONLY a JSON object in this format:

{"sql": "SELECT ..."}
"""


WITH_SCHEMA_PROMPT = """
You are a SQL generation assistant.

Use ONLY the exact table and column names provided below.
Never invent tables or columns.

SCHEMA:

{schema}

Respond with ONLY a JSON object in this format:

{{"sql": "SELECT ..."}}
"""


def parse_sql(text: str) -> str | None:
    """Extract SQL from the LLM JSON response."""

    text = text.strip()

    try:
        return json.loads(text).get("sql")

    except json.JSONDecodeError:

        match = re.search(
            r"\{.*\}",
            text,
            re.DOTALL
        )

        if match:

            try:
                return json.loads(
                    match.group(0)
                ).get("sql")

            except json.JSONDecodeError:
                pass

    return None


def run_sql(sql: str):
    """Execute generated SQL and return result or error."""

    conn = None
    cur = None

    try:
        conn = psycopg2.connect(
            config.DATABASE_URL
        )

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


def main():

    client = get_llm_client()

    # ============================================================
    # TEST A — NO SCHEMA
    # ============================================================

    print("=" * 80)
    print("TEST A -- NO SCHEMA PROVIDED")
    print("=" * 80)

    resp = client.complete(
        NO_SCHEMA_PROMPT,
        [
            {
                "role": "user",
                "content": QUESTION
            }
        ]
    )

    print("\nRAW RESPONSE:")
    print(resp.content)

    sql_a = parse_sql(resp.content)

    print("\nPARSED SQL:")
    print(sql_a)

    if sql_a:

        result, error = run_sql(sql_a)

        print("\nEXECUTION RESULT:")

        if error is None:
            print(result)
        else:
            print("ERROR:", error)

    # ============================================================
    # TEST B — REAL SCHEMA
    # ============================================================

    print()
    print("=" * 80)
    print("TEST B -- REAL SCHEMA PROVIDED")
    print("=" * 80)

    schema = get_schema_summary()

    prompt = WITH_SCHEMA_PROMPT.format(
        schema=schema
    )

    resp = client.complete(
        prompt,
        [
            {
                "role": "user",
                "content": QUESTION
            }
        ]
    )

    print("\nRAW RESPONSE:")
    print(resp.content)

    sql_b = parse_sql(resp.content)

    print("\nPARSED SQL:")
    print(sql_b)

    if sql_b:

        result, error = run_sql(sql_b)

        print("\nEXECUTION RESULT:")

        if error is None:
            print(result)
        else:
            print("ERROR:", error)


if __name__ == "__main__":
    main()