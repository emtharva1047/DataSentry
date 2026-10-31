"""SQLAlchemy models for DataSentry dataset metadata."""
from datetime import datetime
from sqlalchemy import DateTime, Integer, String, func, text
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
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encoding: Mapped[str] = mapped_column(String(20), nullable=False, default="utf-8", server_default=text("'utf-8'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
