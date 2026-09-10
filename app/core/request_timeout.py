from concurrent.futures import ThreadPoolExecutor, TimeoutError


REQUEST_TIMEOUT_SECONDS = 120


class RequestTimeoutError(Exception):
    """Raised when an agent request exceeds the allowed time."""


def run_with_timeout(func, *args, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs):
    """
    Execute a function with a maximum allowed runtime.

    Raises:
        RequestTimeoutError:
            If the function exceeds the configured timeout.
    """

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            func,
            *args,
            **kwargs,
        )

        try:
            return future.result(timeout=timeout)

        except TimeoutError as e:
            future.cancel()

            raise RequestTimeoutError(
                f"Agent request exceeded the "
                f"{timeout}-second timeout."
            ) from e