"""
Exact stored values of low-cardinality text columns, read from the live
database statistics (pg_stats), for the SQL generator's context.

Why: the model otherwise guesses spellings such as 'completed' or 'female'
when the data stores 'Complete' or 'F'. Nothing here is hardcoded: any text
column with a small, fully listed set of values is included, so the hints
follow the data. If statistics are missing, the hints are simply empty.
"""

import psycopg2

import config

MAX_DISTINCT = 20

EXCLUDED_TABLES = {"document_embeddings", "agent_request_metrics"}

_QUERY = """
    SELECT s.tablename, s.attname,
           s.most_common_vals::text::text[] AS vals,
           s.n_distinct
    FROM pg_stats s
    JOIN information_schema.columns c
      ON c.table_schema = s.schemaname
     AND c.table_name = s.tablename
     AND c.column_name = s.attname
    WHERE s.schemaname = 'public'
      AND c.data_type IN ('text', 'character varying')
      AND s.n_distinct >= 1
      AND s.n_distinct <= %s
    ORDER BY s.tablename, s.attname
"""


def format_value_hints(rows, max_distinct=MAX_DISTINCT) -> str:
    """rows: (table, column, values or None, n_distinct). Pure, for testing."""

    lines = []

    for table, column, values, n_distinct in rows:

        if table in EXCLUDED_TABLES or not values:
            continue

        # Only trust the list when it covers every distinct value.
        if len(values) < n_distinct or len(values) > max_distinct:
            continue

        shown = ", ".join(f"'{v}'" for v in sorted(values))
        lines.append(f"- {table}.{column}: {shown}")

    if not lines:
        return ""

    return (
        "Stored values of small text columns (use this exact spelling "
        "and case):\n" + "\n".join(lines)
    )


def get_value_hints() -> str:

    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        try:
            cur = conn.cursor()
            cur.execute(_QUERY, (MAX_DISTINCT,))
            rows = cur.fetchall()
            cur.close()
        finally:
            conn.close()

        return format_value_hints(rows)

    except Exception:
        return ""
