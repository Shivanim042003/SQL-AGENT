import psycopg2
import config


def save_request_metrics(
    request_id: str,
    retry_count: int,
    error_type: str,
    total_latency: float,
    success: bool,
):
    """
    Persist metrics for a completed agent request.
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
                    created_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW()
                );
                """,
                (
                    request_id,
                    retry_count,
                    error_type,
                    total_latency,
                    success,
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
                    created_at
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