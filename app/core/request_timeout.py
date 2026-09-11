import threading
from queue import Queue
from typing import Any, Callable


# ---------------------------------------------------------
# Maximum time allowed for one complete agent request
# ---------------------------------------------------------

REQUEST_TIMEOUT_SECONDS = 600


class RequestTimeoutError(Exception):
    """Raised when an agent request exceeds the allowed time."""


def run_with_timeout(
    func: Callable[..., Any],
    *args,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    **kwargs,
) -> Any:
    """
    Execute a function with a maximum caller wait time.

    Important:
        Python threads cannot be forcibly terminated safely.

        If the timeout is reached, this function raises
        RequestTimeoutError to the caller. The worker thread may
        continue running in the background until the function
        itself finishes.

    Args:
        func:
            Function to execute.

        *args:
            Positional arguments for the function.

        timeout:
            Maximum number of seconds to wait.

        **kwargs:
            Keyword arguments for the function.

    Returns:
        The function's return value.

    Raises:
        RequestTimeoutError:
            If the function does not finish within the timeout.

        Exception:
            Any exception raised by the worker function.
    """

    result_queue = Queue(maxsize=1)

    def worker():
        """
        Execute the target function in a daemon thread.
        """

        try:
            result = func(
                *args,
                **kwargs,
            )

            result_queue.put(
                (
                    "success",
                    result,
                )
            )

        except Exception as e:
            result_queue.put(
                (
                    "error",
                    e,
                )
            )

    thread = threading.Thread(
        target=worker,
        daemon=True,
        name="agent-request-worker",
    )

    thread.start()

    try:
        status, value = result_queue.get(
            timeout=timeout
        )

    except Exception:
        raise RequestTimeoutError(
            f"Agent request exceeded the "
            f"{timeout}-second timeout."
        )

    if status == "error":
        raise value

    return value