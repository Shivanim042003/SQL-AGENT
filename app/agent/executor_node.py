import psycopg2
import config

from app.core.error_types import ErrorType


def execute_sql(state):
    """
    Execute generated SQL against the read-only database.

    Error classification:
        - SQL_GENERATION_ERROR -> no SQL was provided
        - SQL_TIMEOUT          -> database query exceeded timeout
        - SQL_EXECUTION_ERROR  -> known PostgreSQL/database error
        - UNKNOWN_ERROR        -> unexpected Python/runtime error
        - NONE                 -> successful execution
    """

    sql = state.get("sql")

    # ---------------------------------------------------------
    # 1. No SQL generated
    # ---------------------------------------------------------
    if not sql:
        return {
            "query_result": None,
            "error": "No SQL was generated.",
            "error_type": ErrorType.SQL_GENERATION_ERROR.value,
        }

    # ---------------------------------------------------------
    # 2. Never execute without the read-only database URL
    # ---------------------------------------------------------
    if not config.READONLY_DATABASE_URL:
        return {
            "query_result": None,
            "error": (
                "READONLY_DATABASE_URL is not set -- "
                "refusing to execute with a more privileged connection."
            ),
            "error_type": ErrorType.SQL_EXECUTION_ERROR.value,
        }

    conn = None
    cur = None

    try:
        # -----------------------------------------------------
        # 3. Connect using read-only database credentials
        # -----------------------------------------------------
        conn = psycopg2.connect(
            config.READONLY_DATABASE_URL
        )

        # -----------------------------------------------------
        # 4. Create cursor
        # -----------------------------------------------------
        cur = conn.cursor()

        # -----------------------------------------------------
        # 5. Protect database with statement timeout
        # -----------------------------------------------------
        cur.execute(
            "SET statement_timeout = '15s';"
        )

        # -----------------------------------------------------
        # 6. Execute generated SQL
        # -----------------------------------------------------
        cur.execute(sql)

        # -----------------------------------------------------
        # 7. Extract column names
        # -----------------------------------------------------
        columns = [
            description[0]
            for description in cur.description
        ]

        # -----------------------------------------------------
        # 8. Fetch rows
        # -----------------------------------------------------
        rows = cur.fetchall()

        # -----------------------------------------------------
        # 9. Convert rows to dictionaries
        # -----------------------------------------------------
        results = [
            dict(zip(columns, row))
            for row in rows
        ]

        # -----------------------------------------------------
        # 10. Successful execution
        # -----------------------------------------------------
        return {
            "query_result": results,
            "error": None,
            "error_type": ErrorType.NONE.value,
        }

    # ---------------------------------------------------------
    # 11. PostgreSQL query timeout
    # ---------------------------------------------------------
    except psycopg2.errors.QueryCanceledError as e:

        error_message = str(e)

        if "statement timeout" in error_message.lower():
            return {
                "query_result": None,
                "error": error_message,
                "error_type": ErrorType.SQL_TIMEOUT.value,
            }

        return {
            "query_result": None,
            "error": error_message,
            "error_type": ErrorType.SQL_EXECUTION_ERROR.value,
        }

    # ---------------------------------------------------------
    # 12. Other PostgreSQL/database errors
    # ---------------------------------------------------------
    except psycopg2.Error as e:
        return {
            "query_result": None,
            "error": str(e),
            "error_type": ErrorType.SQL_EXECUTION_ERROR.value,
        }

    # ---------------------------------------------------------
    # 13. Unexpected Python/runtime errors
    # ---------------------------------------------------------
    except Exception as e:
        return {
            "query_result": None,
            "error": str(e),
            "error_type": ErrorType.UNKNOWN_ERROR.value,
        }

    # ---------------------------------------------------------
    # 14. Always clean up resources
    #
    # Cleanup itself must NEVER overwrite the original
    # database/error classification.
    # ---------------------------------------------------------
    finally:

        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass

        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass