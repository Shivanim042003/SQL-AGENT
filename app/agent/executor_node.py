import psycopg2

import config


def execute_sql(state):
    """Execute generated SQL through the read-only database role."""

    sql = state.get("sql")

    if not sql:
        return {
            "query_result": None,
            "error": "No SQL was generated."
        }

    if not config.READONLY_DATABASE_URL:
        return {
            "query_result": None,
            "error": (
                "READONLY_DATABASE_URL is not set -- refusing to execute "
                "with a more privileged connection."
            )
        }

    conn = None
    cur = None

    try:
        conn = psycopg2.connect(config.READONLY_DATABASE_URL)
        cur = conn.cursor()

        # Stop expensive queries from running indefinitely
        cur.execute("SET statement_timeout = '15s';")

        cur.execute(sql)

        columns = [
            description[0]
            for description in cur.description
        ]

        rows = cur.fetchall()

        results = [
            dict(zip(columns, row))
            for row in rows
        ]

        return {
            "query_result": results,
            "error": None
        }

    except Exception as e:
        return {
            "query_result": None,
            "error": str(e)
        }

    finally:
        if cur is not None:
            cur.close()

        if conn is not None:
            conn.close()