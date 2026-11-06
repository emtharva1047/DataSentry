"""SQLAlchemy models for source datasets and immutable derived versions."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Dataset(Base):
    """Metadata for an uploaded dataset; content is stored separately."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    rows_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    columns_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_size_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encoding: Mapped[str] = mapped_column(
        String(20), nullable=False, default="utf-8", server_default=text("'utf-8'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DatasetVersion(Base):
    """Immutable, explicitly applied cleaning output derived from a dataset."""

    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataset_versions.id"), nullable=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    rows_count: Mapped[int] = mapped_column(Integer, nullable=False)
    columns_count: Mapped[int] = mapped_column(Integer, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    operations_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
