"""FastAPI application entry point for DataSentry."""
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import get_db, initialize_database
from .models import Dataset  # noqa: F401
from .schemas import DatasetRead
from .services.dataset_ingestion import DatasetTooLargeError, DatasetValidationError, MAX_UPLOAD_BYTES, create_dataset
from .services.dataset_profiling import DatasetFileUnavailableError, profile_dataset

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create and migrate SQLite tables when the API starts."""
    initialize_database()
    yield

app = FastAPI(
    title="DataSentry API",
    description="Dataset quality assessment and ML-readiness research prototype.",
    version="0.2.0",
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
    return {"service": "DataSentry API", "docs": "/docs"}

@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "DataSentry API"}

@app.get("/api/overview", tags=["system"])
def overview(db: Session = Depends(get_db)) -> dict[str, str | int]:
    dataset_count = db.scalar(select(func.count()).select_from(Dataset)) or 0
    return {"api": "online", "database": "connected", "database_engine": "SQLite", "dataset_count": dataset_count}

@app.post("/api/datasets/upload", response_model=DatasetRead, status_code=status.HTTP_201_CREATED, tags=["datasets"])
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Dataset:
    """Validate and persist one CSV without exposing its server-side path."""
    try:
        payload = await file.read(MAX_UPLOAD_BYTES + 1)
        return create_dataset(file.filename, payload, db)
    except DatasetTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except DatasetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()

@app.get("/api/datasets", response_model=list[DatasetRead], tags=["datasets"])
def list_datasets(db: Session = Depends(get_db)) -> list[Dataset]:
    statement = select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id.desc())
    return list(db.scalars(statement).all())

@app.get("/api/datasets/{dataset_id}/profile", tags=["profiling"])
def get_dataset_profile(dataset_id: int, db: Session = Depends(get_db)) -> dict:
    """Return a read-only statistical profile for an uploaded CSV."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        return profile_dataset(dataset)
    except DatasetFileUnavailableError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@app.get("/api/datasets/{dataset_id}", response_model=DatasetRead, tags=["datasets"])
def get_dataset(dataset_id: int, db: Session = Depends(get_db)) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset
