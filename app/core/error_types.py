from enum import Enum


class ErrorType(str, Enum):
    """
    Standard error categories used throughout the SQL agent.
    """

    # No error occurred.
    NONE = "NONE"

    # LLM/provider/client failure.
    LLM_ERROR = "LLM_ERROR"

    # LLM responded but SQL could not be generated/parsed.
    SQL_GENERATION_ERROR = "SQL_GENERATION_ERROR"

    # SQL was generated but database execution failed.
    SQL_EXECUTION_ERROR = "SQL_EXECUTION_ERROR"

    # SQL execution exceeded the configured timeout.
    SQL_TIMEOUT = "SQL_TIMEOUT"

    # Critic LLM or critic response failed.
    CRITIC_ERROR = "CRITIC_ERROR"

    # User request was identified as destructive.
    SAFETY_BLOCK = "SAFETY_BLOCK"

    # Unexpected/unclassified failure.
    UNKNOWN_ERROR = "UNKNOWN_ERROR"