from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
from app.core.rate_limit import RateLimiter
from app.core.validation import MAX_QUESTION_LENGTH
from app.mcp_server.server import ask_database


app = FastAPI(
    title="SQL Agent API",
    description="HTTP API for the self-correcting SQL agent",
    version="1.0.0",
)


# Allow the React frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


limiter = RateLimiter(
    per_minute=config.RATE_LIMIT_PER_MINUTE,
    daily_cap=config.DAILY_REQUEST_CAP,
)


def _client_key(request: Request) -> str:
    # Behind Render's proxy the real client is the first X-Forwarded-For entry.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class QueryRequest(BaseModel):
    question: str = Field(max_length=MAX_QUESTION_LENGTH)


class QueryResponse(BaseModel):
    answer: str


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/query", response_model=QueryResponse)
def query_database(request: QueryRequest, http_request: Request):
    allowed, reason = limiter.check(_client_key(http_request))
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    answer = ask_database(request.question)

    return QueryResponse(
        answer=answer
    )