"""Public API schemas; internal storage paths are never returned."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class DatasetRead(BaseModel):
    """Safe dataset metadata returned to the web client."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    rows_count: int
    columns_count: int
    file_size_bytes: int
    sha256_hash: str | None
    encoding: str
    created_at: datetime
