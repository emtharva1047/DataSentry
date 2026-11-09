"""FastAPI application entry point for DataSentry."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import get_db, initialize_database
from .models import Dataset, DatasetVersion  # noqa: F401
from .schemas import (
    AnomalyDetectionRequest,
    CleaningRequest,
    DatasetRead,
    DatasetSchemaValidationRequest,
)
from .services.dataset_ingestion import (
    DatasetTooLargeError,
    DatasetValidationError,
    MAX_UPLOAD_BYTES,
    create_dataset,
)
from .services.dataset_profiling import DatasetFileUnavailableError, profile_dataset
from .services.dataset_quality import DatasetQualityFileUnavailableError, assess_dataset_quality
from .services.dataset_schema_validation import validate_dataset_schema
from .services.dataset_anomaly import (
    DatasetAnomalyFileUnavailableError,
    DatasetAnomalyRequestError,
    detect_dataset_anomalies,
)
from .services.dataset_cleaning import (
    DatasetCleaningFileUnavailableError,
    DatasetCleaningNoChangesError,
    DatasetCleaningRequestError,
    apply_cleaning,
    get_cleaning_recommendations,
    list_dataset_versions,
    preview_cleaning,
)
from .services.dataset_comparison import compare_dataset_version_quality


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create and migrate SQLite tables when the API starts."""
    initialize_database()
    yield


app = FastAPI(
    title="DataSentry API",
    description="Dataset quality assessment and ML-readiness research prototype.",
    version="0.4.0",
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
    return {
        "api": "online",
        "database": "connected",
        "database_engine": "SQLite",
        "dataset_count": dataset_count,
    }


@app.post(
    "/api/datasets/upload",
    response_model=DatasetRead,
    status_code=status.HTTP_201_CREATED,
    tags=["datasets"],
)
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


@app.get("/api/datasets/{dataset_id}/quality", tags=["quality"])
def get_dataset_quality(dataset_id: int, db: Session = Depends(get_db)) -> dict:
    """Return inferred quality issues and an explainable DQS without mutating data."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        return assess_dataset_quality(dataset)
    except DatasetQualityFileUnavailableError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@app.post("/api/datasets/{dataset_id}/quality/validate", tags=["quality"])
def post_dataset_schema_validation(
    dataset_id: int,
    request: DatasetSchemaValidationRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Validate a dataset against explicit caller-supplied schema/domain constraints."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        return validate_dataset_schema(dataset, request.model_dump())
    except DatasetQualityFileUnavailableError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@app.post("/api/datasets/{dataset_id}/anomalies", tags=["anomalies"])
def post_dataset_anomalies(
    dataset_id: int,
    request: AnomalyDetectionRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Return deterministic anomaly review flags without changing source data."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        return detect_dataset_anomalies(dataset, request.model_dump())
    except DatasetAnomalyRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatasetAnomalyFileUnavailableError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@app.get("/api/datasets/{dataset_id}/cleaning/recommendations", tags=["cleaning"])
def get_dataset_cleaning_recommendations(
    dataset_id: int,
    base_version_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Return advisory cleaning recommendations without changing source data."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        return get_cleaning_recommendations(dataset, db, base_version_id)
    except DatasetCleaningRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatasetCleaningFileUnavailableError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@app.post("/api/datasets/{dataset_id}/cleaning/preview", tags=["cleaning"])
def post_dataset_cleaning_preview(
    dataset_id: int,
    request: CleaningRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Preview explicitly selected cleaning operations without persisting changes."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        return preview_cleaning(dataset, request.model_dump(), db)
    except DatasetCleaningRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatasetCleaningFileUnavailableError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@app.post(
    "/api/datasets/{dataset_id}/cleaning/apply",
    status_code=status.HTTP_201_CREATED,
    tags=["cleaning"],
)
def post_dataset_cleaning_apply(
    dataset_id: int,
    request: CleaningRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Apply only the requested operations and create a new immutable dataset version."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        return apply_cleaning(dataset, request.model_dump(), db)
    except DatasetCleaningRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatasetCleaningNoChangesError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatasetCleaningFileUnavailableError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@app.get("/api/datasets/{dataset_id}/cleaning/versions", tags=["cleaning"])
def get_dataset_cleaning_versions(
    dataset_id: int, db: Session = Depends(get_db)
) -> list[dict]:
    """List immutable versions created from one uploaded dataset."""
    if db.get(Dataset, dataset_id) is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return list_dataset_versions(dataset_id, db)


@app.get(
    "/api/datasets/{dataset_id}/cleaning/versions/{version_id}/quality-comparison",
    tags=["cleaning"],
)
def get_dataset_version_quality_comparison(
    dataset_id: int, version_id: int, db: Session = Depends(get_db)
) -> dict:
    """Compare the original upload's DQS with one immutable derived version."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    version = db.get(DatasetVersion, version_id)
    if version is None or version.dataset_id != dataset_id:
        raise HTTPException(status_code=404, detail="Dataset version not found.")
    try:
        return compare_dataset_version_quality(dataset, version)
    except (DatasetQualityFileUnavailableError, DatasetFileUnavailableError) as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc


@app.get("/api/datasets/{dataset_id}", response_model=DatasetRead, tags=["datasets"])
def get_dataset(dataset_id: int, db: Session = Depends(get_db)) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset
