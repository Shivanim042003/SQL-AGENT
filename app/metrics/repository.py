import psycopg2
import json
import config


def save_request_metrics(
    request_id: str,
    retry_count: int,
    error_type: str,
    total_latency: float,
    success: bool,
    latencies: dict | None = None,
    retry_latencies: dict | None = None,
):
    """
    Persist metrics for a completed agent request.

    In addition to basic request metrics, persist:
    - cumulative stage latency
    - per-attempt retry latency
    """

    conn = psycopg2.connect(
        config.DATABASE_URL
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO agent_request_metrics (
                    request_id,
                    retry_count,
                    error_type,
                    total_latency,
                    success,
                    created_at,
                    latencies,
                    retry_latencies
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW(),
                    %s::jsonb,
                    %s::jsonb
                );
                """,
                (
                    request_id,
                    retry_count,
                    error_type,
                    total_latency,
                    success,
                    json.dumps(
                        latencies or {}
                    ),
                    json.dumps(
                        retry_latencies or {}
                    ),
                ),
            )

        conn.commit()

    finally:
        conn.close()


def get_recent_request_metrics(limit: int = 20):
    """
    Return the most recent persisted request metrics.
    """

    if limit <= 0:
        raise ValueError(
            "limit must be greater than 0"
        )

    conn = psycopg2.connect(
        config.DATABASE_URL
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    request_id,
                    retry_count,
                    error_type,
                    total_latency,
                    success,
                    created_at,
                    latencies,
                    retry_latencies
                FROM agent_request_metrics
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (limit,),
            )

            rows = cursor.fetchall()

            return [
                {
                    "request_id": str(row[0]),
                    "retry_count": row[1],
                    "error_type": row[2],
                    "total_latency": row[3],
                    "success": row[4],
                    "created_at": row[5].isoformat(),
                    "latencies": row[6],
                    "retry_latencies": row[7],
                }
                for row in rows
            ]

    finally:
        conn.close()


def get_request_statistics():
    """
    Return aggregate statistics from persisted request metrics.
    """

    conn = psycopg2.connect(
        config.DATABASE_URL
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_requests,

                    COUNT(*) FILTER (
                        WHERE success = TRUE
                    ) AS successful_requests,

                    COUNT(*) FILTER (
                        WHERE success = FALSE
                    ) AS failed_requests,

                    COALESCE(
                        ROUND(
                            AVG(total_latency)::numeric,
                            4
                        ),
                        0
                    ) AS average_latency,

                    COALESCE(
                        ROUND(
                            AVG(retry_count)::numeric,
                            4
                        ),
                        0
                    ) AS average_retries,

                    COALESCE(
                        ROUND(
                            (
                                COUNT(*) FILTER (
                                    WHERE success = TRUE
                                )::numeric
                                / NULLIF(COUNT(*), 0)
                            ) * 100,
                            2
                        ),
                        0
                    ) AS success_rate_percent

                FROM agent_request_metrics;
                """
            )

            row = cursor.fetchone()

            return {
                "total_requests": row[0],
                "successful_requests": row[1],
                "failed_requests": row[2],
                "average_latency": float(row[3]),
                "average_retries": float(row[4]),
                "success_rate_percent": float(row[5]),
            }

    finally:
        conn.close()


def get_error_statistics():
    """
    Return aggregate request counts grouped by error type.
    """

    conn = psycopg2.connect(
        config.DATABASE_URL
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    error_type,
                    COUNT(*) AS request_count
                FROM agent_request_metrics
                GROUP BY error_type
                ORDER BY request_count DESC;
                """
            )

            rows = cursor.fetchall()

            return {
                row[0]: row[1]
                for row in rows
            }

    finally:
        conn.close()


def delete_old_request_metrics(
    retention_days: int = 30,
):
    """
    Delete persisted request metrics older than
    the configured retention period.

    Returns:
        Number of deleted rows.
    """

    if retention_days <= 0:
        raise ValueError(
            "retention_days must be greater than 0"
        )

    conn = psycopg2.connect(
        config.DATABASE_URL
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM agent_request_metrics
                WHERE created_at <
                    NOW() - (%s * INTERVAL '1 day');
                """,
                (retention_days,),
            )

            deleted_rows = cursor.rowcount

        conn.commit()

        return deleted_rows

    finally:
        conn.close()

def get_stage_latency_statistics():
    """
    Return average latency for each agent stage
    across persisted requests.
    """

    conn = psycopg2.connect(
        config.DATABASE_URL
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COALESCE(
                        AVG((latencies ->> 'intent')::double precision),
                        0
                    ) AS intent,

                    COALESCE(
                        AVG((latencies ->> 'schema')::double precision),
                        0
                    ) AS schema,

                    COALESCE(
                        AVG((latencies ->> 'retrieval')::double precision),
                        0
                    ) AS retrieval,

                    COALESCE(
                        AVG((latencies ->> 'sql_generation')::double precision),
                        0
                    ) AS sql_generation,

                    COALESCE(
                        AVG((latencies ->> 'execution')::double precision),
                        0
                    ) AS execution,

                    COALESCE(
                        AVG((latencies ->> 'critic')::double precision),
                        0
                    ) AS critic,

                    COALESCE(
                        AVG((latencies ->> 'answer')::double precision),
                        0
                    ) AS answer,

                    COALESCE(
                        AVG((latencies ->> 'total')::double precision),
                        0
                    ) AS total

                FROM agent_request_metrics;
                """
            )

            row = cursor.fetchone()

            return {
                "intent": round(float(row[0]), 4),
                "schema": round(float(row[1]), 4),
                "retrieval": round(float(row[2]), 4),
                "sql_generation": round(float(row[3]), 4),
                "execution": round(float(row[4]), 4),
                "critic": round(float(row[5]), 4),
                "answer": round(float(row[6]), 4),
                "total": round(float(row[7]), 4),
            }

    finally:
        conn.close()     

def get_retry_latency_statistics():
    """
    Return aggregate latency statistics for retry attempts.
    """

    conn = psycopg2.connect(
        config.DATABASE_URL
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    retry_latencies
                FROM agent_request_metrics
                WHERE retry_latencies <> '{}'::jsonb;
                """
            )

            rows = cursor.fetchall()

            attempt_totals = {}

            for row in rows:
                retry_latencies = row[0]

                if not retry_latencies:
                    continue

                for attempt, stages in retry_latencies.items():

                    if attempt not in attempt_totals:
                        attempt_totals[attempt] = {
                            "count": 0,
                            "total_latency": 0.0,
                        }

                    attempt_total = sum(
                        float(value)
                        for value in stages.values()
                    )

                    attempt_totals[attempt]["count"] += 1

                    attempt_totals[attempt][
                        "total_latency"
                    ] += attempt_total

            statistics = {}

            for attempt, values in attempt_totals.items():

                statistics[attempt] = {
                    "request_count": values["count"],
                    "average_latency": round(
                        values["total_latency"]
                        / values["count"],
                        4,
                    ),
                }

            return statistics

    finally:
        conn.close()           

def reset_request_metrics():
    """
    Delete all persisted request metrics.

    Intended for development and testing only.
    """

    conn = psycopg2.connect(
        config.DATABASE_URL
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM agent_request_metrics;
                """
            )

            deleted_rows = cursor.rowcount

        conn.commit()

        return deleted_rows

    finally:
        conn.close()  

def reset_request_metrics():
    """
    Delete all persisted request metrics.

    Intended for development and testing only.
    """

    conn = psycopg2.connect(
        config.DATABASE_URL
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM agent_request_metrics;
                """
            )

            deleted_rows = cursor.rowcount

        conn.commit()

        return deleted_rows

    finally:
        conn.close()              