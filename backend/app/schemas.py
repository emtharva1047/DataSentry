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


class CleaningRequest(BaseModel):
    """Explicit operations to preview or apply to a source or prior version."""

    model_config = ConfigDict(extra="forbid")

    base_version_id: int | None = Field(default=None, ge=1)
    drop_exact_duplicates: bool = False
    fill_numeric_median: list[str] = Field(default_factory=list, max_length=200)
    fill_categorical_mode: list[str] = Field(default_factory=list, max_length=200)
    trim_whitespace: list[str] = Field(default_factory=list, max_length=200)
    lowercase_categories: list[str] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def validate_operations(self) -> "CleaningRequest":
        operations = (
            self.fill_numeric_median,
            self.fill_categorical_mode,
            self.trim_whitespace,
            self.lowercase_categories,
        )
        for columns in operations:
            if len(columns) != len(set(columns)):
                raise ValueError("a column may appear only once within an operation")
            if any(not name.strip() or len(name) > 255 for name in columns):
                raise ValueError("column names must be non-empty and at most 255 characters")
        if not self.drop_exact_duplicates and not any(operations):
            raise ValueError("select at least one explicit cleaning operation")
        return self


class MLReadinessRequest(BaseModel):
    """Target and feature selection for deterministic ML-readiness diagnostics."""

    model_config = ConfigDict(extra="forbid")

    target_column: str = Field(min_length=1, max_length=255)
    task_type: Literal["classification", "regression"]
    feature_columns: list[str] | None = Field(default=None, min_length=1, max_length=200)
    leakage_threshold: float = Field(default=0.995, ge=0.8, le=1.0, allow_inf_nan=False)
    correlation_threshold: float = Field(default=0.95, ge=0.5, le=1.0, allow_inf_nan=False)
    min_class_count: int = Field(default=5, ge=1, le=1000)
    majority_class_threshold: float = Field(default=0.8, gt=0.5, le=1.0, allow_inf_nan=False)

    @field_validator("target_column")
    @classmethod
    def validate_target_column(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("target_column must not be blank")
        return value

    @field_validator("feature_columns")
    @classmethod
    def validate_feature_columns(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if any(not name.strip() or len(name) > 255 for name in value):
            raise ValueError("feature column names must be non-empty and at most 255 characters")
        if len(value) != len(set(value)):
            raise ValueError("feature_columns must not contain duplicates")
        return value


class MLBaselineRequest(BaseModel):
    """Seeded holdout configuration for one baseline classification or regression."""

    model_config = ConfigDict(extra="forbid")

    target_column: str = Field(min_length=1, max_length=255)
    task_type: Literal["classification", "regression"]
    feature_columns: list[str] | None = Field(default=None, min_length=1, max_length=200)
    test_size: float = Field(default=0.25, gt=0.1, lt=0.5, allow_inf_nan=False)
    random_state: int = Field(default=42, ge=0, le=4_294_967_295)

    @field_validator("target_column")
    @classmethod
    def validate_baseline_target(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("target_column must not be blank")
        return value

    @field_validator("feature_columns")
    @classmethod
    def validate_baseline_features(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if any(not name.strip() or len(name) > 255 for name in value):
            raise ValueError("feature column names must be non-empty and at most 255 characters")
        if len(value) != len(set(value)):
            raise ValueError("feature_columns must not contain duplicates")
        return value
