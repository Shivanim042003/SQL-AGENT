import logging
import sys


def configure_logging():
    """
    Configure application-wide logging.

    Logs are written to stderr so that stdout remains clean
    for protocols such as MCP stdio.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
        stream=sys.stderr,
        force=True,
    )