"""Configurable runtime data locations for SQLite, uploads, and immutable versions."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def resolve_data_dir(configured: str | None = None) -> Path:
    """Resolve DATASENTRY_DATA_DIR, defaulting to the backend directory."""
    raw = configured if configured is not None else os.environ.get("DATASENTRY_DATA_DIR")
    if raw is None or not raw.strip():
        return BACKEND_DIR
    return Path(raw).expanduser().resolve()


DATA_DIR = resolve_data_dir()
UPLOAD_DIR = DATA_DIR / "uploads"
VERSIONS_DIR = DATA_DIR / "versions"
