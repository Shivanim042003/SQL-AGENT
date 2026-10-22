from fastapi.testclient import TestClient

import app.api as api


def test_rate_limit_returns_429(monkeypatch):
    monkeypatch.setattr(api, "ask_database", lambda q: "ok")
    monkeypatch.setattr(api, "limiter", api.RateLimiter(per_minute=1))
    c = TestClient(api.app)
    assert c.post("/api/query", json={"question": "hi"}).status_code == 200
    r = c.post("/api/query", json={"question": "hi"})
    assert r.status_code == 429
    assert "Too many" in r.json()["detail"]


def test_overlong_question_rejected(monkeypatch):
    monkeypatch.setattr(api, "ask_database", lambda q: "ok")
    c = TestClient(api.app)
    assert c.post("/api/query", json={"question": "x" * 5000}).status_code == 422
