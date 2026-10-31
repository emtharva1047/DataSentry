"""API tests for read-only CSV profiling."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import dataset_ingestion


@pytest.fixture
def profile_client(tmp_path, monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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


def test_profile_reports_missingness_numeric_and_categorical_distribution(profile_client):
    client, _ = profile_client
    csv_bytes = (
        b"age,salary,department,score\n"
        b"20,50000,Sales,0.8\n"
        b"30,60000,Sales,0.7\n"
        b",,Engineering,0.9\n"
        b"40,70000,Engineering,0.6\n"
    )
    uploaded = client.post(
        "/api/datasets/upload",
        files={"file": ("staff.csv", csv_bytes, "text/csv")},
    )
    assert uploaded.status_code == 201
    dataset_id = uploaded.json()["id"]

    response = client.get(f"/api/datasets/{dataset_id}/profile")

    assert response.status_code == 200
    profile = response.json()
    assert profile["shape"] == {"rows": 4, "columns": 4}
    assert profile["missing_cells"] == 2
    assert profile["total_cells"] == 16
    assert profile["numeric_column_count"] == 3
    assert profile["categorical_column_count"] == 1

    columns = {column["name"]: column for column in profile["columns"]}
    assert columns["age"]["inferred_type"] == "integer"
    assert columns["age"]["missing_count"] == 1
    assert columns["age"]["unique_count"] == 3
    assert columns["age"]["numeric_summary"]["mean"] == 30.0
    assert sum(item["count"] for item in columns["age"]["histogram"]) == 3
    assert columns["department"]["inferred_type"] == "categorical"
    assert columns["department"]["top_values"] == [
        {"value": "Sales", "count": 2},
        {"value": "Engineering", "count": 2},
    ]
    assert profile["correlations"]["method"] == "pearson"
    assert profile["correlations"]["columns"] == ["age", "salary", "score"]


def test_profile_returns_404_for_unknown_dataset(profile_client):
    response = profile_client[0].get("/api/datasets/9999/profile")
    assert response.status_code == 404


def test_profile_returns_gone_when_stored_csv_is_missing(profile_client):
    client, upload_dir = profile_client
    uploaded = client.post(
        "/api/datasets/upload",
        files={"file": ("temporary.csv", b"value\n1\n2\n", "text/csv")},
    )
    assert uploaded.status_code == 201
    dataset_id = uploaded.json()["id"]
    stored_file = next(upload_dir.glob("*.csv"))
    stored_file.unlink()

    response = client.get(f"/api/datasets/{dataset_id}/profile")
    assert response.status_code == 410
    assert "unavailable" in response.json()["detail"].lower()
