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

# Optional. Sent as "reasoning_effort" (low/medium/high) when set; for hosted
# reasoning models such as gpt-oss. Empty = not sent.
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "")

# Lower bound for max_tokens. Reasoning models spend output tokens on thinking,
# so the generator's small budget (256) can leave an empty answer.
LLM_MIN_MAX_TOKENS = int(os.getenv("LLM_MIN_MAX_TOKENS", "0") or 0)

# Evaluation only. DISABLE_SHORTCUTS=1 turns off the hardcoded SQL for known
# questions and the hardcoded critic acceptance rules, so every answer comes
# from the model (used by eval/run_ablation.py).
DISABLE_SHORTCUTS = os.getenv("DISABLE_SHORTCUTS", "0") == "1"

# Accuracy aids added after the ablation. Both default on; set to 0 to
# reproduce the earlier behaviour for a before/after comparison.
VALUE_HINTS = os.getenv("VALUE_HINTS", "1") == "1"
RETRY_GUARD = os.getenv("RETRY_GUARD", "1") == "1"

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
