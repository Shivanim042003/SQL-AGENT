import httpx
import pytest

from app.core.rate_limit import RateLimiter
from app.llm.openai_compatible_client import OpenAICompatibleClient
from app.retrieval.openai_compatible_embeddings import OpenAICompatibleEmbeddingClient


def _client(handler, **kw):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatibleClient(
        model="m", base_url="https://x/v1/", api_key="k", http_client=http, **kw
    )


def _ok(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_complete_sends_system_and_strips_think(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.read().decode()
        return _ok("<think>hmm</think>  hello ")

    r = _client(handler).complete("SYS", [{"role": "user", "content": "q"}], max_tokens=5, think=False)
    assert r.content == "hello"
    assert seen["url"] == "https://x/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    assert '"role":"system"' in seen["body"].replace(" ", "")


def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429) if len(calls) < 3 else _ok("ok")

    assert _client(handler).complete("s", []).content == "ok"
    assert len(calls) == 3


def test_raises_after_exhausted_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="429"):
        _client(lambda r: httpx.Response(429, text="slow down")).complete("s", [])


def test_client_error_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, text="bad key")

    with pytest.raises(RuntimeError, match="401"):
        _client(handler).complete("s", [])
    assert len(calls) == 1


def test_missing_api_key_rejected(monkeypatch):
    monkeypatch.setattr("config.LLM_API_KEY", "")
    with pytest.raises(ValueError):
        OpenAICompatibleClient(model="m", base_url="https://x")


def _emb(handler, dims=3):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatibleEmbeddingClient(
        model="e", base_url="https://x/v1", api_key="k", dimensions=dims, http_client=http
    )


def test_embeddings_ordered_by_index():
    def handler(request):
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [4, 5, 6]},
            {"index": 0, "embedding": [1, 2, 3]},
        ]})

    assert _emb(handler).embed(["a", "b"]) == [[1, 2, 3], [4, 5, 6]]


def test_embeddings_too_short_rejected():
    def handler(request):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]})

    with pytest.raises(ValueError, match="dimensions"):
        _emb(handler).embed(["a"])


def test_embeddings_longer_vector_truncated_and_normalised():
    def handler(request):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [3, 4, 9, 9]}]})

    v = _emb(handler, dims=2).embed(["a"])[0]
    assert v == pytest.approx([0.6, 0.8])


def test_embeddings_batched_and_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    sizes = []

    def handler(request):
        import json
        n = len(json.loads(request.read())["input"])
        if not sizes:
            sizes.append("429")
            return httpx.Response(429)
        sizes.append(n)
        return httpx.Response(200, json={"data": [
            {"index": i, "embedding": [1, 2, 3]} for i in range(n)
        ]})

    out = _emb(handler).embed([str(i) for i in range(120)])
    assert len(out) == 120
    assert sizes == ["429", 50, 50, 20]


def test_rate_limiter_per_minute_and_daily_cap():
    t = [1000.0]
    rl = RateLimiter(per_minute=2, daily_cap=3, clock=lambda: t[0])
    assert rl.check("a")[0] and rl.check("a")[0]
    assert not rl.check("a")[0]          # minute limit
    assert rl.check("b")[0]              # other client ok (3rd of day)
    assert not rl.check("c")[0]          # daily cap reached
    t[0] += 86400
    assert rl.check("c")[0]              # new day resets


def test_reasoning_effort_and_token_floor(monkeypatch):
    import json
    monkeypatch.setattr("config.LLM_REASONING_EFFORT", "low")
    monkeypatch.setattr("config.LLM_MIN_MAX_TOKENS", 1024)
    seen = {}

    def handler(request):
        seen.update(json.loads(request.read()))
        return _ok("x")

    _client(handler).complete("s", [], max_tokens=256)
    assert seen["reasoning_effort"] == "low"
    assert seen["max_tokens"] == 1024


def test_reasoning_effort_omitted_by_default(monkeypatch):
    import json
    monkeypatch.setattr("config.LLM_REASONING_EFFORT", "")
    seen = {}

    def handler(request):
        seen.update(json.loads(request.read()))
        return _ok("x")

    _client(handler).complete("s", [], max_tokens=256)
    assert "reasoning_effort" not in seen
    assert seen["max_tokens"] == 256
