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
