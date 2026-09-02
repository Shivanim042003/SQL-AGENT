import json
import re

from app.llm.factory import get_llm_client

DESTRUCTIVE_CHECK_PROMPT = """You are the safety-check step of a data-analyst agent operating on a READ-ONLY database. Given a user's question, decide whether it asks to modify, delete, update, insert, or drop any data -- in any phrasing, however indirect.

Respond with ONLY a JSON object, no other text:
{"is_destructive": true}
or
{"is_destructive": false}
"""


def _parse_bool(text: str) -> bool:
    text = text.strip()
    try:
        return bool(json.loads(text).get("is_destructive", False))
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return bool(json.loads(match.group(0)).get("is_destructive", False))
            except json.JSONDecodeError:
                pass
    return True


def check_intent(state) -> dict:
    client = get_llm_client()
    response = client.complete(
        DESTRUCTIVE_CHECK_PROMPT,
        [{"role": "user", "content": state["question"]}],
    )
    return {"is_destructive": _parse_bool(response.content)}