"""Public API schemas; internal storage paths are never returned."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ColumnSchema(BaseModel):
    """Explicit expectations for one CSV column."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["string", "integer", "number", "boolean"] = "string"
    required: bool = False
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)
    allowed_values: list[str] | None = Field(default=None, min_length=1, max_length=1000)
    case_sensitive: bool = True

    @model_validator(mode="after")
    def validate_constraints(self) -> "ColumnSchema":
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError("minimum must be less than or equal to maximum")
        if self.type not in {"integer", "number"} and (
            self.minimum is not None or self.maximum is not None
        ):
            raise ValueError("minimum and maximum are supported only for integer or number columns")
        return self


class DatasetSchemaValidationRequest(BaseModel):
    """Caller-supplied schema and domain constraints for read-only validation."""

    model_config = ConfigDict(extra="forbid")

    columns: dict[str, ColumnSchema] = Field(min_length=1, max_length=200)
    allow_extra_columns: bool = False

    @field_validator("columns")
    @classmethod
    def validate_column_names(cls, value: dict[str, ColumnSchema]) -> dict[str, ColumnSchema]:
        invalid = [name for name in value if not name.strip() or len(name) > 255]
        if invalid:
            raise ValueError("schema column names must be non-empty and at most 255 characters")
        return value


class AnomalyDetectionRequest(BaseModel):
    """Reproducible parameters for read-only numerical anomaly detection."""

    model_config = ConfigDict(extra="forbid")

    detectors: list[Literal["iqr", "robust_zscore", "isolation_forest"]] = Field(
        default_factory=lambda: ["iqr", "robust_zscore", "isolation_forest"],
        min_length=1,
        max_length=3,
    )
    columns: list[str] | None = Field(default=None, min_length=1, max_length=200)
    iqr_multiplier: float = Field(default=1.5, gt=0, le=10, allow_inf_nan=False)
    robust_z_threshold: float = Field(default=3.5, gt=0, le=20, allow_inf_nan=False)
    contamination: float = Field(default=0.05, gt=0, le=0.5, allow_inf_nan=False)
    random_state: int = Field(default=42, ge=0, le=4_294_967_295)
    n_estimators: int = Field(default=100, ge=50, le=500)
    max_evidence_rows: int = Field(default=20, ge=1, le=100)

    @field_validator("detectors")
    @classmethod
    def validate_detectors(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("detectors must not contain duplicates")
        return value

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if any(not name.strip() or len(name) > 255 for name in value):
            raise ValueError("column names must be non-empty and at most 255 characters")
        if len(value) != len(set(value)):
            raise ValueError("columns must not contain duplicates")
        return value
