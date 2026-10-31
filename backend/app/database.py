"""SQLite engine, sessions, and additive schema migration."""
from collections.abc import Generator
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATABASE_PATH = BACKEND_DIR / "datasentry.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

def initialize_database() -> None:
    """Create tables and add columns to SQLite files from earlier prototypes."""
    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("datasets")}
    migrations = {
        "file_size_bytes": "ALTER TABLE datasets ADD COLUMN file_size_bytes INTEGER NOT NULL DEFAULT 0",
        "sha256_hash": "ALTER TABLE datasets ADD COLUMN sha256_hash VARCHAR(64)",
        "encoding": "ALTER TABLE datasets ADD COLUMN encoding VARCHAR(20) NOT NULL DEFAULT 'utf-8'",
    }
    with engine.begin() as connection:
        for name, statement in migrations.items():
            if name not in columns:
                connection.execute(text(statement))

def get_db() -> Generator[Session, None, None]:
    """Yield a database session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
