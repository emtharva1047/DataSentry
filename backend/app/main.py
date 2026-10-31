"""FastAPI application entry point for DataSentry."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Dataset  # noqa: F401 — registers model metadata


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create initial SQLite tables when the API starts."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="DataSentry API",
    description="Dataset quality assessment and ML-readiness research prototype.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Return API welcome information."""
    return {"service": "DataSentry API", "docs": "/docs"}


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    """Return API liveness."""
    return {"status": "ok", "service": "DataSentry API"}


@app.get("/api/overview", tags=["system"])
def overview(db: Session = Depends(get_db)) -> dict[str, str | int]:
    """Return backend and database status plus the current dataset count."""
    dataset_count = db.scalar(select(func.count()).select_from(Dataset)) or 0
    return {
        "api": "online",
        "database": "connected",
        "database_engine": "SQLite",
        "dataset_count": dataset_count,
    }
