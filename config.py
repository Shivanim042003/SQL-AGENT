import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent

# Dataset configuration
ACTIVE_DATASET = os.getenv("ACTIVE_DATASET", "thelook")

DATASET_DIR = PROJECT_ROOT / "datasets" / ACTIVE_DATASET
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / ACTIVE_DATASET

# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:8b")

# Embedding configuration
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "qwen3-embedding:0.6b"
)

# Ollama configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Database configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB", "agentic_data_analyst")

DATABASE_URL = os.getenv("DATABASE_URL")