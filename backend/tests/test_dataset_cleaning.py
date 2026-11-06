"""Tests for advisory cleaning, read-only preview, and immutable versions."""
import hashlib
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import dataset_cleaning, dataset_ingestion


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)
    upload_dir = tmp_path / "uploads"
    version_dir = tmp_path / "versions"
    monkeypatch.setattr(dataset_ingestion, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(dataset_cleaning, "VERSIONS_DIR", version_dir)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, upload_dir, version_dir
    app.dependency_overrides.clear()
    test_engine.dispose()


def upload(client):
    payload = (
        b"amount,city,category\n"
        b"10, New York ,Retail\n"
        b",New York,retail\n"
        b"10, New York ,Retail\n"
        b"20,,Retail\n"
    )
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sample.csv", payload, "text/csv")},
    )
    assert response.status_code == 201
    return response.json(), payload


def test_recommendations_are_advisory_and_identify_safe_candidates(client):
    test_client, upload_dir, version_dir = client
    dataset, payload = upload(test_client)
    response = test_client.get(
        f"/api/datasets/{dataset['id']}/cleaning/recommendations"
    )
    assert response.status_code == 200
    body = response.json()
    operations = {item["operation"] for item in body["recommendations"]}
    assert {
        "drop_exact_duplicates",
        "fill_numeric_median",
        "fill_categorical_mode",
        "trim_whitespace",
        "lowercase_categories",
    }.issubset(operations)
    case = next(
        item for item in body["recommendations"]
        if item["operation"] == "lowercase_categories"
    )
    assert case["recommended"] is False
    assert list(version_dir.glob("*.csv")) == []
    assert list(upload_dir.glob("*.csv"))[0].read_bytes() == payload


def test_preview_is_bounded_and_does_not_modify_source_or_create_version(client):
    test_client, upload_dir, version_dir = client
    dataset, payload = upload(test_client)
    request = {
        "drop_exact_duplicates": True,
        "fill_numeric_median": ["amount"],
        "trim_whitespace": ["city"],
        "fill_categorical_mode": ["city"],
    }
    response = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/preview", json=request
    )
    assert response.status_code == 200
    body = response.json()
    assert body["changed"] is True
    assert body["rows_before"] == 4
    assert body["rows_after"] == 3
    assert body["preview"]["removed_row_count"] == 1
    assert body["preview"]["changed_row_count"] >= 2
    assert len(body["preview"]["sample_rows"]) <= 10
    assert list(version_dir.glob("*.csv")) == []
    stored = list(upload_dir.glob("*.csv"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == payload
    assert body["source_sha256"] == hashlib.sha256(payload).hexdigest()


def test_apply_creates_immutable_version_and_preserves_original(client):
    test_client, upload_dir, version_dir = client
    dataset, payload = upload(test_client)
    request = {
        "drop_exact_duplicates": True,
        "fill_numeric_median": ["amount"],
        "trim_whitespace": ["city"],
    }
    response = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/apply", json=request
    )
    assert response.status_code == 201
    body = response.json()
    version = body["version"]
    assert version["version_number"] == 1
    assert version["parent_version_id"] is None
    assert version["rows_count"] == 3
    assert body["source_preserved"] is True
    assert len(list(version_dir.glob("*.csv"))) == 1
    original = list(upload_dir.glob("*.csv"))[0]
    assert original.read_bytes() == payload
    assert hashlib.sha256(original.read_bytes()).hexdigest() == dataset["sha256_hash"]
    cleaned_path = next(version_dir.glob("*.csv"))
    cleaned = pd.read_csv(cleaned_path)
    assert cleaned["amount"].isna().sum() == 0
    assert cleaned["city"].dropna().str.strip().eq(cleaned["city"].dropna()).all()
    assert "storage_path" not in version


def test_versions_can_be_chained_without_overwriting_prior_version(client):
    test_client, _, version_dir = client
    dataset, _ = upload(test_client)
    first = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/apply",
        json={"trim_whitespace": ["city"]},
    )
    assert first.status_code == 201
    first_version = first.json()["version"]
    first_path = next(version_dir.iterdir())
    first_bytes = first_path.read_bytes()

    second = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/apply",
        json={
            "base_version_id": first_version["id"],
            "lowercase_categories": ["category"],
        },
    )
    assert second.status_code == 201
    second_version = second.json()["version"]
    assert second_version["version_number"] == 2
    assert second_version["parent_version_id"] == first_version["id"]
    assert first_path.read_bytes() == first_bytes
    assert len(list(version_dir.glob("*.csv"))) == 2

    versions = test_client.get(
        f"/api/datasets/{dataset['id']}/cleaning/versions"
    )
    assert versions.status_code == 200
    assert [item["version_number"] for item in versions.json()] == [1, 2]
    assert all("storage_path" not in item for item in versions.json())


def test_rejects_unknown_column_and_foreign_base_version(client):
    test_client, _, _ = client
    dataset, _ = upload(test_client)
    unknown = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/preview",
        json={"trim_whitespace": ["not_a_column"]},
    )
    assert unknown.status_code == 422
    other, _ = upload(test_client)
    other_version = test_client.post(
        f"/api/datasets/{other['id']}/cleaning/apply",
        json={"trim_whitespace": ["city"]},
    )
    assert other_version.status_code == 201
    foreign_version = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/preview",
        json={
            "base_version_id": other_version.json()["version"]["id"],
            "trim_whitespace": ["city"],
        },
    )
    assert foreign_version.status_code == 422
    assert other["id"] != dataset["id"]


def test_noop_apply_does_not_create_version(client):
    test_client, _, version_dir = client
    dataset, _ = upload(test_client)
    response = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/apply",
        json={"trim_whitespace": ["category"]},
    )
    assert response.status_code == 409
    assert list(version_dir.glob("*.csv")) == []


def test_numeric_median_rejects_mixed_non_numeric_values(client):
    test_client, _, version_dir = client
    response = test_client.post(
        "/api/datasets/upload",
        files={
            "file": (
                "mixed.csv",
                b"amount\n10\nunknown\n\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    dataset_id = response.json()["id"]
    preview = test_client.post(
        f"/api/datasets/{dataset_id}/cleaning/preview",
        json={"fill_numeric_median": ["amount"]},
    )
    assert preview.status_code == 422
    assert "non-numeric" in preview.json()["detail"]
    assert list(version_dir.glob("*.csv")) == []
