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