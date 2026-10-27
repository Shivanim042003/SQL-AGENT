"""Process-wide counter of LLM calls and tokens (used by the ablation eval)."""

import threading

_lock = threading.Lock()
_totals = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}


def record(prompt_tokens: int | None, completion_tokens: int | None) -> None:
    with _lock:
        _totals["calls"] += 1
        _totals["prompt_tokens"] += int(prompt_tokens or 0)
        _totals["completion_tokens"] += int(completion_tokens or 0)


def snapshot() -> dict:
    with _lock:
        return dict(_totals)


def delta(before: dict, after: dict | None = None) -> dict:
    """Usage between two snapshots (``after`` defaults to now)."""
    after = after or snapshot()
    return {key: after[key] - before.get(key, 0) for key in after}


def reset() -> None:
    with _lock:
        for key in _totals:
            _totals[key] = 0
