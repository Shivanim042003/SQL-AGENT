import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

import psycopg2
import config


# document_embeddings is retrieval infrastructure,
# not business/domain data.
EXCLUDED_TABLES = {"document_embeddings", "agent_request_metrics"}


def get_schema_summary() -> str:
    """
    Get real, current table and column names directly from PostgreSQL.
    """

    conn = psycopg2.connect(config.DATABASE_URL)
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                table_name,
                column_name,
                data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)

        rows = cur.fetchall()

        tables = {}

        for table, column, data_type in rows:

            if table in EXCLUDED_TABLES:
                continue

            tables.setdefault(table, []).append(
                f"{column} ({data_type})"
            )

        return "\n".join(
            f"{table}: {', '.join(columns)}"
            for table, columns in tables.items()
        )

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    print(get_schema_summary())