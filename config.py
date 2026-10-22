import os
from pathlib import Path

from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()


# =========================
# Project Paths
# =========================

PROJECT_ROOT = Path(__file__).resolve().parent


# =========================
# Dataset Configuration
# =========================

ACTIVE_DATASET = os.getenv("ACTIVE_DATASET", "thelook")

DATASET_DIR = PROJECT_ROOT / "datasets" / ACTIVE_DATASET

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / ACTIVE_DATASET


# =========================
# LLM Configuration
# =========================

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:8b")

# Model for the destructive-intent safety check. A smaller, faster model
# is fine here; defaults to LLM_MODEL so behaviour is unchanged unless set.
INTENT_MODEL = os.getenv("INTENT_MODEL") or LLM_MODEL

# Hosted, OpenAI-compatible provider (LLM_PROVIDER=openai_compatible).
# Example (Groq): LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")

LLM_API_KEY = os.getenv("LLM_API_KEY", "")

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://127.0.0.1:11434"
)


# =========================
# Embedding Configuration
# =========================

EMBEDDING_PROVIDER = os.getenv(
    "EMBEDDING_PROVIDER",
    "ollama"
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "qwen3-embedding:0.6b"
)


# Hosted embeddings (EMBEDDING_PROVIDER=openai_compatible).
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "")

EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")

# If set, vectors of any other length are rejected (table is vector(1024)).
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "0") or 0)


# =========================
# Public API Settings
# =========================

# Comma-separated list of allowed browser origins.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

# Per-client requests per minute, and a global cap per day (0 disables).
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "6"))

DAILY_REQUEST_CAP = int(os.getenv("DAILY_REQUEST_CAP", "0"))


# =========================
# PostgreSQL Configuration
# =========================

POSTGRES_USER = os.getenv("POSTGRES_USER")

POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

POSTGRES_DB = os.getenv("POSTGRES_DB")

DATABASE_URL = os.environ["DATABASE_URL"]


# =========================
# Read-Only Database Configuration
# =========================

READONLY_DATABASE_URL = os.getenv(
    "READONLY_DATABASE_URL"
)

# =========================
# Optional Fast Paths
# =========================

# When "1", skip the LLM critic for plain single-table COUNT(*) questions.
SKIP_CRITIC_FOR_SIMPLE_COUNTS = os.getenv("SKIP_CRITIC_FOR_SIMPLE_COUNTS", "0") == "1"
# Retrieval Database Configuration
# =========================

RETRIEVAL_DATABASE_URL = os.getenv("RETRIEVAL_DATABASE_URL")
