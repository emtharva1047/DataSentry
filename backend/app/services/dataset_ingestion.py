"""Validated CSV ingestion and dataset metadata persistence."""
import csv
import hashlib
import io
import re
import unicodedata
import uuid
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError, ParserError
from sqlalchemy.orm import Session
from ..models import Dataset

BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BACKEND_DIR / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 200

class DatasetValidationError(ValueError):
    """Raised when uploaded content is not a supported CSV."""

class DatasetTooLargeError(DatasetValidationError):
    """Raised when the configured upload, row, or column limit is exceeded."""

def _safe_filename(filename: str | None) -> str:
    """Keep a display basename; never use user input as a storage path."""
    name = (filename or "dataset.csv").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(c for c in name if unicodedata.category(c) != "Cc").strip()
    return re.sub(r"\s+", " ", name)[:255] or "dataset.csv"

def _parse_csv(filename: str | None, payload: bytes) -> tuple[str, pd.DataFrame, str]:
    if Path((filename or "").replace("\\", "/")).suffix.lower() != ".csv":
        raise DatasetValidationError("Only .csv files are supported.")
    if not payload:
        raise DatasetValidationError("The uploaded CSV is empty.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise DatasetTooLargeError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.")
    if b"\x00" in payload:
        raise DatasetValidationError("The file contains binary data, not a text CSV.")

    decoded = None
    encoding = ""
    for candidate in ("utf-8-sig", "cp1252"):
        try:
            decoded = payload.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise DatasetValidationError("Could not decode CSV. Save it as UTF-8 or Windows-1252.")

    try:
        header = next(csv.reader(io.StringIO(decoded, newline="")), None)
    except csv.Error as exc:
        raise DatasetValidationError(f"Could not parse CSV header: {exc}") from exc
    if not header or not any(value.strip() for value in header):
        raise DatasetValidationError("CSV must contain a non-empty header row.")
    if len(header) > MAX_COLUMNS:
        raise DatasetTooLargeError(f"CSV has {len(header)} columns; the limit is {MAX_COLUMNS}.")
    if any(not value.strip() for value in header):
        raise DatasetValidationError("Column names cannot be blank.")
    normalized = [value.strip().casefold() for value in header]
    if len(normalized) != len(set(normalized)):
        raise DatasetValidationError("Column names must be unique, ignoring case and surrounding spaces.")

    try:
        frame = pd.read_csv(io.StringIO(decoded), nrows=MAX_ROWS + 1, on_bad_lines="error")
    except (EmptyDataError, ParserError, UnicodeDecodeError, ValueError) as exc:
        raise DatasetValidationError(f"Could not parse CSV: {exc}") from exc
    if len(frame.columns) != len(header):
        raise DatasetValidationError("Parsed column count does not match the CSV header.")
    if frame.empty:
        raise DatasetValidationError("CSV must contain at least one data row.")
    if len(frame) > MAX_ROWS:
        raise DatasetTooLargeError(f"CSV exceeds the {MAX_ROWS:,} row limit.")
    return _safe_filename(filename), frame, encoding

def create_dataset(filename: str | None, payload: bytes, db: Session) -> Dataset:
    """Validate content, store under a generated UUID, and persist metadata."""
    safe_name, frame, encoding = _parse_csv(filename, payload)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.csv"
    with stored_path.open("xb") as handle:
        handle.write(payload)
    dataset = Dataset(
        filename=safe_name,
        original_path=str(stored_path),
        rows_count=int(frame.shape[0]),
        columns_count=int(frame.shape[1]),
        file_size_bytes=len(payload),
        sha256_hash=hashlib.sha256(payload).hexdigest(),
        encoding=encoding,
    )
    try:
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
    except Exception:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise
    return dataset
