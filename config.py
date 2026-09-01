import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent

ACTIVE_DATASET = os.getenv("ACTIVE_DATASET", "thelook")

DATASET_DIR = PROJECT_ROOT / "datasets" / ACTIVE_DATASET
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / ACTIVE_DATASET

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3")