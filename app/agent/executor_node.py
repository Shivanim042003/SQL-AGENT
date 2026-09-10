import psycopg2
import config

from app.core.error_types import ErrorType
from app.core.timing import measure_latency


def execute_sql(state):
    """
    Execute generated SQL against the read-only database.

    Error classification:
        - SQL_GENERATION_ERROR -> no SQL was provided
        - SQL_TIMEOUT          -> database query exceeded timeout
        - SQL_EXECUTION_ERROR  -> known PostgreSQL/database error
        - UNKNOWN_ERROR        -> unexpected Python/runtime error
        - NONE                 -> successful execution

    Latency:
        - cumulative execution latency
        - per-attempt execution latency
    """

    # --------------------------------------------------------
    # Preserve cumulative latency
    # --------------------------------------------------------

    latencies = dict(
        state.get("latencies", {})
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
    # --------------------------------------------------------

    attempt = state.get(
        "retry_count",
        0
    )

    # --------------------------------------------------------
    # Get SQL
    # --------------------------------------------------------

    sql = state.get("sql")

    if not sql:
        return {
            "query_result": None,
            "error": "No SQL was generated.",
            "error_type": ErrorType.SQL_GENERATION_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Require read-only database URL
    # --------------------------------------------------------

    if not config.READONLY_DATABASE_URL:
        return {
            "query_result": None,
            "error": (
                "READONLY_DATABASE_URL is not set -- "
                "refusing to execute with a more privileged connection."
            ),
            "error_type": ErrorType.SQL_EXECUTION_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    conn = None
    cur = None

    try:

        # ----------------------------------------------------
        # Measure database execution
        # ----------------------------------------------------

        with measure_latency(
            latencies,
            "execution",
            attempt=attempt,
            retry_latencies=retry_latencies
        ):

            conn = psycopg2.connect(
                config.READONLY_DATABASE_URL
            )

            cur = conn.cursor()

            cur.execute(
                "SET statement_timeout = '15s';"
            )

            cur.execute(sql)

            columns = [
                description[0]
                for description in cur.description
            ]

            rows = cur.fetchall()

            results = [
                dict(
                    zip(
                        columns,
                        row
                    )
                )
                for row in rows
            ]

        return {
            "query_result": results,
            "error": None,
            "error_type": ErrorType.NONE.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # PostgreSQL timeout
    # --------------------------------------------------------

    except psycopg2.errors.QueryCanceledError as e:

        error_message = str(e)

        if "statement timeout" in error_message.lower():
            return {
                "query_result": None,
                "error": error_message,
                "error_type": ErrorType.SQL_TIMEOUT.value,
                "latencies": latencies,
                "retry_latencies": retry_latencies,
            }

        return {
            "query_result": None,
            "error": error_message,
            "error_type": ErrorType.SQL_EXECUTION_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Other PostgreSQL errors
    # --------------------------------------------------------

    except psycopg2.Error as e:

        return {
            "query_result": None,
            "error": str(e),
            "error_type": ErrorType.SQL_EXECUTION_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Unexpected error
    # --------------------------------------------------------

    except Exception as e:

        return {
            "query_result": None,
            "error": str(e),
            "error_type": ErrorType.UNKNOWN_ERROR.value,
            "latencies": latencies,
            "retry_latencies": retry_latencies,
        }

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

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