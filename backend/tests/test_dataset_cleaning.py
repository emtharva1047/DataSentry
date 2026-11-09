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



def test_version_quality_comparison_reports_dqs_deltas_without_mutation(client):
    test_client, upload_dir, version_dir = client
    dataset, payload = upload(test_client)
    apply_response = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/apply",
        json={
            "drop_exact_duplicates": True,
            "fill_numeric_median": ["amount"],
            "fill_categorical_mode": ["city"],
            "trim_whitespace": ["city"],
        },
    )
    assert apply_response.status_code == 201
    version = apply_response.json()["version"]
    original_path = next(upload_dir.glob("*.csv"))
    version_path = next(version_dir.glob("*.csv"))
    original_bytes = original_path.read_bytes()
    version_bytes = version_path.read_bytes()

    response = test_client.get(
        f"/api/datasets/{dataset['id']}/cleaning/versions/"
        f"{version['id']}/quality-comparison"
    )

    assert response.status_code == 200
    comparison = response.json()
    assert comparison["before"]["source_version_id"] is None
    assert comparison["after"]["source_version_id"] == version["id"]
    assert comparison["after"]["version_number"] == version["version_number"]
    assert comparison["before"]["source_sha256"] == dataset["sha256_hash"]
    assert comparison["after"]["source_sha256"] == version["sha256_hash"]
    assert comparison["delta"]["rows"] == -1
    assert comparison["delta"]["overall"] > 0
    assert comparison["delta"]["components"]["completeness"]["score_delta"] > 0
    assert comparison["delta"]["components"]["uniqueness"]["score_delta"] > 0
    assert original_path.read_bytes() == original_bytes == payload
    assert version_path.read_bytes() == version_bytes


def test_version_quality_comparison_rejects_foreign_version(client):
    test_client, _, _ = client
    first_dataset, _ = upload(test_client)
    applied = test_client.post(
        f"/api/datasets/{first_dataset['id']}/cleaning/apply",
        json={"trim_whitespace": ["city"]},
    )
    assert applied.status_code == 201
    version_id = applied.json()["version"]["id"]
    second_dataset, _ = upload(test_client)

    response = test_client.get(
        f"/api/datasets/{second_dataset['id']}/cleaning/versions/"
        f"{version_id}/quality-comparison"
    )

    assert response.status_code == 404


def test_version_quality_comparison_returns_gone_for_missing_version_file(client):
    test_client, _, version_dir = client
    dataset, _ = upload(test_client)
    applied = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/apply",
        json={"trim_whitespace": ["city"]},
    )
    assert applied.status_code == 201
    version_id = applied.json()["version"]["id"]
    next(version_dir.glob("*.csv")).unlink()

    response = test_client.get(
        f"/api/datasets/{dataset['id']}/cleaning/versions/"
        f"{version_id}/quality-comparison"
    )

    assert response.status_code == 410



def test_version_quality_comparison_includes_aligned_numeric_profiles_and_correlations(client):
    test_client, upload_dir, version_dir = client
    payload = (
        b"amount,units,category\n"
        b"10,1,Retail\n"
        b",2, Retail \n"
        b"30,3,Retail\n"
        b"100,4,Retail\n"
    )
    uploaded = test_client.post(
        "/api/datasets/upload",
        files={"file": ("numeric.csv", payload, "text/csv")},
    )
    assert uploaded.status_code == 201
    dataset = uploaded.json()

    applied = test_client.post(
        f"/api/datasets/{dataset['id']}/cleaning/apply",
        json={
            "fill_numeric_median": ["amount"],
            "trim_whitespace": ["category"],
        },
    )
    assert applied.status_code == 201
    version = applied.json()["version"]
    original_path = next(upload_dir.glob("*.csv"))
    version_path = next(version_dir.glob("*.csv"))
    original_bytes = original_path.read_bytes()
    version_bytes = version_path.read_bytes()

    response = test_client.get(
        f"/api/datasets/{dataset['id']}/cleaning/versions/"
        f"{version['id']}/quality-comparison"
    )

    assert response.status_code == 200
    profile = response.json()["profile_comparison"]
    amount = next(item for item in profile["numeric_columns"] if item["column"] == "amount")
    assert amount["status"] == "comparable"
    assert amount["summary_deltas"]["mean"] != 0
    assert amount["histogram_bins_comparable"] is True
    assert len(amount["before_histogram"]) == 10
    assert len(amount["after_histogram"]) == 10
    assert [
        (item["bin_start"], item["bin_end"]) for item in amount["before_histogram"]
    ] == [
        (item["bin_start"], item["bin_end"]) for item in amount["after_histogram"]
    ]

    pair = next(
        item for item in profile["correlations"]["pairs"]
        if {item["left_column"], item["right_column"]} == {"amount", "units"}
    )
    assert pair["delta"] != 0
    assert profile["correlations"]["comparable_pair_count"] >= 1
    assert original_path.read_bytes() == original_bytes == payload
    assert version_path.read_bytes() == version_bytes
