"""Tests for configurable runtime storage locations."""
from app.storage import BACKEND_DIR, resolve_data_dir


def test_resolve_data_dir_uses_explicit_path(tmp_path):
    configured = tmp_path / "isolated" / "state"
    assert resolve_data_dir(str(configured)) == configured.resolve()


def test_resolve_data_dir_uses_environment(monkeypatch, tmp_path):
    configured = tmp_path / "from-env"
    monkeypatch.setenv("DATASENTRY_DATA_DIR", str(configured))
    assert resolve_data_dir() == configured.resolve()


def test_resolve_data_dir_defaults_to_backend(monkeypatch):
    monkeypatch.delenv("DATASENTRY_DATA_DIR", raising=False)
    assert resolve_data_dir() == BACKEND_DIR
