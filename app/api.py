from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.mcp_server.server import ask_database


app = FastAPI(
    title="SQL Agent API",
    description="HTTP API for the self-correcting SQL agent",
    version="1.0.0",
)


# Allow the React frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/query", response_model=QueryResponse)
def query_database(request: QueryRequest):
    answer = ask_database(request.question)

    return QueryResponse(
        answer=answer
    )