"""
Pytest bootstrap.

The unit tests never connect to a database or to Ollama, but config.py reads
DATABASE_URL at import time. Load .env if there is one (local development);
otherwise fall back to placeholder values so a fresh clone can run the tests.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")