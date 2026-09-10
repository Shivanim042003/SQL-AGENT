from collections import Counter


class RequestMetrics:
    """
    Lightweight in-memory metrics for agent requests.

    Tracks:
    - total requests
    - successful requests
    - failed requests
    - timeout requests
    - safety-blocked requests
    - total retries
    """

    def __init__(self):
        self._counts = Counter()

    def record_request(self):
        self._counts["total_requests"] += 1

    def record_success(self):
        self._counts["successful_requests"] += 1

    def record_failure(self):
        self._counts["failed_requests"] += 1

    def record_timeout(self):
        self._counts["timeout_requests"] += 1

    def record_safety_block(self):
        self._counts["safety_blocked_requests"] += 1

    def record_retries(self, retry_count: int):
        self._counts["total_retries"] += retry_count

    def snapshot(self) -> dict[str, int | float]:
        """
        Return the current metrics snapshot.
        """

        total_requests = self._counts["total_requests"]

        successful_requests = self._counts[
            "successful_requests"
        ]

        failed_requests = self._counts[
            "failed_requests"
        ]

        timeout_requests = self._counts[
            "timeout_requests"
        ]

        safety_blocked_requests = self._counts[
            "safety_blocked_requests"
        ]

        total_retries = self._counts[
            "total_retries"
        ]

        success_rate = 0.0

        if total_requests > 0:
            success_rate = round(
                successful_requests
                / total_requests
                * 100,
                2,
            )

        average_retries = 0.0

        if total_requests > 0:
            average_retries = round(
                total_retries
                / total_requests,
                2,
            )

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "timeout_requests": timeout_requests,
            "safety_blocked_requests": (
                safety_blocked_requests
            ),
            "total_retries": total_retries,
            "success_rate_percent": success_rate,
            "average_retries_per_request": (
                average_retries
            ),
        }


# Application-wide metrics instance
request_metrics = RequestMetrics()