import json
import re

import config
from app.llm.factory import get_llm_client as _get_llm_client
from app.core.error_types import ErrorType
from app.core.timing import measure_latency


def get_llm_client():
    """Client for the safety check (may use a smaller, faster model)."""
    return _get_llm_client(model=config.INTENT_MODEL)


# ============================================================
# DESTRUCTIVE INTENT PROMPT
# ============================================================

DESTRUCTIVE_CHECK_PROMPT = """
You are the safety-check step of a data-analyst agent operating on a
READ-ONLY database.

Given a user's question, decide whether the request asks to:

- modify data
- delete data
- update data
- insert data
- drop data
- alter database structures
- truncate data
- perform any other destructive database operation

This includes indirect or natural-language phrasing.

Examples of destructive requests:

"delete all users"
"remove all purchase events"
"update the customer records"
"drop the events table"
"insert a new user"
"change every user's email"

Examples of non-destructive requests:

"how many users are there?"
"what is the conversion rate?"
"show me purchase events"
"how many sessions happened yesterday?"

Respond with ONLY a JSON object:

{"is_destructive": true}

or:

{"is_destructive": false}
"""


# ============================================================
# PARSE BOOLEAN
# ============================================================

def _parse_bool(text: str) -> tuple[bool, bool]:
    """
    Parse the destructive classification.

    Returns:
        (is_destructive, parse_success)
    """

    if not text:
        return False, False

    text = text.strip()

    # --------------------------------------------------------
    # Direct JSON
    # --------------------------------------------------------

    try:
        data = json.loads(text)

        if not isinstance(data, dict):
            return False, False

        value = data.get("is_destructive")

        if isinstance(value, bool):
            return value, True

        return False, False

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # JSON embedded in surrounding text
    # --------------------------------------------------------

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL
    )

    if match:

        try:

            data = json.loads(
                match.group(0)
            )

            if not isinstance(data, dict):
                return False, False

            value = data.get(
                "is_destructive"
            )

            if isinstance(value, bool):
                return value, True

        except json.JSONDecodeError:
            pass

    return False, False


# ============================================================
# INTENT NODE
# ============================================================

def check_intent(state) -> dict:
    """
    Determine whether the user request is destructive.

    Safety principle:

    If the safety LLM itself fails, do NOT continue into the
    SQL pipeline.

    The request is therefore stopped and classified as LLM_ERROR.

    Latency:

    The time spent waiting for the safety LLM is recorded under
    the "intent" latency key.
    """

    # --------------------------------------------------------
    # Existing latency state
    # --------------------------------------------------------

    latencies = dict(
        state.get("latencies", {})
    )

    # --------------------------------------------------------
    # Get LLM client
    # --------------------------------------------------------

    try:

        client = get_llm_client()

    except Exception as e:

        return {
            "is_destructive": False,
            "error": (
                f"Safety intent check failed: {str(e)}"
            ),
            "error_type": ErrorType.LLM_ERROR.value,
        }

    # --------------------------------------------------------
    # Call LLM
    #
    # Only the actual LLM operation is timed here.
    # --------------------------------------------------------

    try:

        with measure_latency(
            latencies,
            "intent"
        ):

            response = client.complete(
                DESTRUCTIVE_CHECK_PROMPT,
                [
                    {
                        "role": "user",
                        "content": state["question"]
                    }
                ]
            )

    except Exception as e:

        return {
            "is_destructive": False,
            "error": (
                f"Safety intent check failed: {str(e)}"
            ),
            "error_type": ErrorType.LLM_ERROR.value,
            "latencies": latencies,
        }

    # --------------------------------------------------------
    # Parse response
    # --------------------------------------------------------

    is_destructive, parse_success = _parse_bool(
        response.content
    )

    # --------------------------------------------------------
    # Invalid safety response
    # --------------------------------------------------------

    if not parse_success:

        return {
            "is_destructive": False,
            "error": (
                "Safety intent check returned "
                "an invalid response."
            ),
            "error_type": ErrorType.LLM_ERROR.value,
            "latencies": latencies,
        }

    # --------------------------------------------------------
    # DESTRUCTIVE REQUEST
    # --------------------------------------------------------

    if is_destructive:

        return {
            "is_destructive": True,
            "error": (
                "Request blocked because it asks "
                "for a destructive database operation."
            ),
            "error_type": ErrorType.SAFETY_BLOCK.value,
            "latencies": latencies,
        }

    # --------------------------------------------------------
    # SAFE REQUEST
    # --------------------------------------------------------

    return {
        "is_destructive": False,
        "error": None,
        "error_type": ErrorType.NONE.value,
        "latencies": latencies,
    }