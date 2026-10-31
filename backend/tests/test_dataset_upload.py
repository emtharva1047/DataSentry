"""Tests for CSV ingestion and dataset metadata endpoints."""
import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import dataset_ingestion

@pytest.fixture
def client(tmp_path, monkeypatch):
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(dataset_ingestion, "UPLOAD_DIR", upload_dir)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, upload_dir
    app.dependency_overrides.clear()
    test_engine.dispose()

def test_upload_persists_metadata_and_generated_storage_name(client):
    test_client, upload_dir = client
    payload = b"name,age\nAsha,21\nRavi,22\n"
    response = test_client.post("/api/datasets/upload", files={"file": ("students.csv", payload, "text/csv")})
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "students.csv"
    assert body["rows_count"] == 2 and body["columns_count"] == 2
    assert body["file_size_bytes"] == len(payload)
    assert body["sha256_hash"] == hashlib.sha256(payload).hexdigest()
    stored = list(upload_dir.glob("*.csv"))
    assert len(stored) == 1 and stored[0].name != "students.csv"
    assert stored[0].read_bytes() == payload
    assert "original_path" not in body

def test_rejects_non_csv(client):
    response = client[0].post("/api/datasets/upload", files={"file": ("data.xlsx", b"bad", "application/octet-stream")})
    assert response.status_code == 422

def test_rejects_duplicate_headers(client):
    response = client[0].post("/api/datasets/upload", files={"file": ("bad.csv", b"name,Name\nA,B\n", "text/csv")})
    assert response.status_code == 422
    assert "unique" in response.json()["detail"].lower()

def test_rejects_empty_csv(client):
    response = client[0].post("/api/datasets/upload", files={"file": ("empty.csv", b"", "text/csv")})
    assert response.status_code == 422

def test_rejects_file_over_limit(client, monkeypatch):
    monkeypatch.setattr(dataset_ingestion, "MAX_UPLOAD_BYTES", 8)
    response = client[0].post("/api/datasets/upload", files={"file": ("large.csv", b"column\n123456789\n", "text/csv")})
    assert response.status_code == 413

def test_list_detail_and_not_found(client):
    test_client, _ = client
    upload = test_client.post("/api/datasets/upload", files={"file": ("items.csv", b"item,qty\nPen,2\n", "text/csv")})
    dataset_id = upload.json()["id"]
    assert test_client.get("/api/datasets").json()[0]["id"] == dataset_id
    assert test_client.get(f"/api/datasets/{dataset_id}").status_code == 200
    assert test_client.get("/api/datasets/9999").status_code == 404

def test_sanitizes_windows_path_in_display_filename(client):
    response = client[0].post("/api/datasets/upload", files={"file": (r"C:\\private\\students.csv", b"name\nAsha\n", "text/csv")})
    assert response.status_code == 201
    assert response.json()["filename"] == "students.csv"
