"""Tests for strict environment-driven API CORS configuration."""
import pytest
from fastapi.middleware.cors import CORSMiddleware

from app.config import DEFAULT_CORS_ORIGINS, get_cors_origins
from app.main import app


def test_unset_cors_configuration_keeps_local_development_origins(monkeypatch):
    monkeypatch.delenv("DATASENTRY_CORS_ORIGINS", raising=False)

    assert get_cors_origins() == list(DEFAULT_CORS_ORIGINS)


def test_cors_configuration_is_loaded_from_environment(monkeypatch):
    monkeypatch.setenv(
        "DATASENTRY_CORS_ORIGINS",
        "https://app.example.com, https://admin.example.com:8443",
    )

    assert get_cors_origins() == [
        "https://app.example.com",
        "https://admin.example.com:8443",
    ]


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("https://APP.example.com:443/", ["https://app.example.com"]),
        ("http://localhost:3000/,http://localhost:3000", ["http://localhost:3000"]),
        ("http://[::1]:8080", ["http://[::1]:8080"]),
        ("https://münich.example", ["https://xn--mnich-kva.example"]),
    ],
)
def test_cors_origins_are_normalized_and_deduplicated(configured, expected):
    assert get_cors_origins(configured) == expected


@pytest.mark.parametrize(
    "configured",
    [
        "",
        " , ",
        "https://app.example.com,",
        "*",
        "https://*.example.com",
        "null",
        "ftp://app.example.com",
        "https://",
        "https://app.example.com/path",
        "https://user:password@app.example.com",
        "https://app.example.com?mode=1",
        "https://app.example.com#section",
        "https://app.example.com:invalid",
        "https://app.example.com:0",
    ],
)
def test_invalid_cors_origins_fail_closed(configured):
    with pytest.raises(ValueError, match="CORS"):
        get_cors_origins(configured)


def test_fastapi_cors_middleware_uses_the_validated_allowlist():
    middleware = next(
        item for item in app.user_middleware if item.cls is CORSMiddleware
    )

    assert middleware.kwargs["allow_origins"] == list(DEFAULT_CORS_ORIGINS)
    assert middleware.kwargs["allow_credentials"] is True
