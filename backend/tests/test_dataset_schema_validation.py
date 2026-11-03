"""API tests for explicit, read-only schema and domain validation."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import dataset_ingestion


@pytest.fixture
def schema_client(tmp_path, monkeypatch):
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


def _upload(client, payload):
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("schema.csv", payload, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_schema_validation_reports_types_ranges_domains_and_columns(schema_client):
    client, upload_dir = schema_client
    payload = (
        b"age,status,score,extra\n"
        b"20,ACTIVE,0.5,x\n"
        b"-3,unknown,2,y\n"
        b"1.5,active,0.7,z\n"
        b",active,0.4,w\n"
    )
    dataset_id = _upload(client, payload)
    original_path = next(upload_dir.glob("*.csv"))
    original_bytes = original_path.read_bytes()

    response = client.post(
        f"/api/datasets/{dataset_id}/quality/validate",
        json={
            "columns": {
                "age": {"type": "integer", "required": True, "minimum": 0, "maximum": 120},
                "status": {
                    "type": "string",
                    "allowed_values": ["active", "inactive"],
                    "case_sensitive": False,
                },
                "score": {"type": "number", "minimum": 0, "maximum": 1},
                "country": {"type": "string", "required": True},
            },
            "allow_extra_columns": False,
        },
    )

    assert response.status_code == 200
    report = response.json()
    issues = {
        f"{issue['code']}:{issue['column']}": issue
        for issue in report["issues"]
    }
    assert "missing_schema_column:country" in issues
    assert "unexpected_schema_column:extra" in issues
    assert "required_values_missing:age" in issues
    assert "schema_type_mismatch:age" in issues
    assert "domain_out_of_range:age" in issues
    assert "domain_value_invalid:status" in issues
    assert "domain_out_of_range:score" in issues

    assert issues["required_values_missing:age"]["evidence"]["row_numbers"] == [4]
    assert issues["schema_type_mismatch:age"]["evidence"]["row_numbers"] == [3]
    assert issues["domain_out_of_range:age"]["evidence"]["row_numbers"] == [2]
    assert issues["domain_value_invalid:status"]["evidence"]["row_numbers"] == [2]
    assert issues["domain_out_of_range:score"]["evidence"]["row_numbers"] == [2]
    assert report["schema_validation"]["passed"] is False
    assert report["schema_validation"]["present_column_count"] == 3
    assert report["schema_validation"]["unexpected_columns"] == ["extra"]
    assert report["issue_count"] == len(report["issues"])
    assert report["issues_by_severity"]["high"] >= 1

    # Schema checks are read-only and do not alter the inference-based DQS endpoint.
    assert original_path.read_bytes() == original_bytes
    base_quality = client.get(f"/api/datasets/{dataset_id}/quality")
    assert base_quality.status_code == 200
    assert "schema_validation" not in base_quality.json()


def test_schema_validation_accepts_valid_values_and_case_insensitive_domain(schema_client):
    client, _ = schema_client
    dataset_id = _upload(
        client,
        b"age,enabled,status\n21,true,ACTIVE\n35,no,inactive\n",
    )

    response = client.post(
        f"/api/datasets/{dataset_id}/quality/validate",
        json={
            "columns": {
                "age": {"type": "integer", "required": True, "minimum": 18, "maximum": 100},
                "enabled": {"type": "boolean"},
                "status": {
                    "type": "string",
                    "allowed_values": ["active", "inactive"],
                    "case_sensitive": False,
                },
            },
            "allow_extra_columns": False,
        },
    )

    assert response.status_code == 200
    report = response.json()
    assert report["schema_validation"]["passed"] is True
    assert report["issue_count"] == 0
    assert report["issues"] == []


def test_schema_validation_rejects_invalid_constraint_configuration(schema_client):
    client, _ = schema_client
    dataset_id = _upload(client, b"age\n20\n")
    response = client.post(
        f"/api/datasets/{dataset_id}/quality/validate",
        json={"columns": {"age": {"type": "integer", "minimum": 10, "maximum": 0}}},
    )
    assert response.status_code == 422


def test_schema_validation_returns_404_for_unknown_dataset(schema_client):
    response = schema_client[0].post(
        "/api/datasets/9999/quality/validate",
        json={"columns": {"age": {"type": "integer"}}},
    )
    assert response.status_code == 404


def test_schema_validation_returns_410_for_missing_source_file(schema_client):
    client, upload_dir = schema_client
    dataset_id = _upload(client, b"age\n20\n")
    next(upload_dir.glob("*.csv")).unlink()
    response = client.post(
        f"/api/datasets/{dataset_id}/quality/validate",
        json={"columns": {"age": {"type": "integer"}}},
    )
    assert response.status_code == 410
