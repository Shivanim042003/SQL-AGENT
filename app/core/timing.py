import time
from contextlib import contextmanager


@contextmanager
def measure_latency(
    latencies: dict[str, float],
    name: str,
    attempt: int | None = None,
    retry_latencies: dict[str, dict[str, float]] | None = None,
):
    """
    Measure execution time of a block.

    Cumulative latency is stored in:

        latencies[name]

    When attempt information is provided, the same measurement
    is also stored in:

        retry_latencies["attempt_X"][name]

    Repeated stage measurements are accumulated.

    Units:
        seconds
    """

    start = time.perf_counter()

    try:
        yield

    finally:
        elapsed = time.perf_counter() - start

        # ----------------------------------------------------
        # Cumulative latency
        # ----------------------------------------------------

        latencies[name] = round(
            latencies.get(name, 0.0) + elapsed,
            4
        )

        # ----------------------------------------------------
        # Per-attempt latency
        # ----------------------------------------------------

        if (
            attempt is not None
            and retry_latencies is not None
        ):
            attempt_key = f"attempt_{attempt}"

            if attempt_key not in retry_latencies:
                retry_latencies[attempt_key] = {}

            retry_latencies[attempt_key][name] = round(
                retry_latencies[attempt_key].get(name, 0.0)
                + elapsed,
                4
            )