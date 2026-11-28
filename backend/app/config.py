"""Validated environment configuration for the DataSentry API."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def get_cors_origins(value: str | None = None) -> list[str]:
    """Return a validated, normalized CORS allowlist.

    DATASENTRY_CORS_ORIGINS is a comma-separated list of exact browser
    origins. An unset variable preserves local-development defaults. An
    explicitly empty or malformed value fails fast rather than silently
    widening or changing the allowlist.
    """
    configured = os.environ.get("DATASENTRY_CORS_ORIGINS") if value is None else value
    if configured is None:
        return list(DEFAULT_CORS_ORIGINS)

    entries = configured.split(",")
    if not configured.strip() or any(not entry.strip() for entry in entries):
        raise ValueError(
            "DATASENTRY_CORS_ORIGINS must contain one or more comma-separated origins."
        )

    origins: list[str] = []
    for entry in entries:
        origin = entry.strip()
        if origin == "null" or "*" in origin:
            raise ValueError("CORS wildcard and opaque 'null' origins are not allowed.")

        try:
            parsed = urlsplit(origin)
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"Invalid CORS origin {origin!r}: {exc}") from exc

        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.netloc
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or "?" in origin
            or "#" in origin
        ):
            raise ValueError(
                f"Invalid CORS origin {origin!r}: expected an HTTP(S) origin "
                "without credentials, path, query, or fragment."
            )

        hostname = parsed.hostname
        if any(character.isspace() or character in "/\\@[]" for character in hostname):
            raise ValueError(f"Invalid hostname in CORS origin {origin!r}.")
        if port is not None and not 1 <= port <= 65535:
            raise ValueError(f"Invalid port in CORS origin {origin!r}.")

        if ":" in hostname:
            normalized_host = f"[{hostname.lower()}]"
        else:
            try:
                normalized_host = hostname.encode("idna").decode("ascii").lower()
            except UnicodeError as exc:
                raise ValueError(f"Invalid hostname in CORS origin {origin!r}.") from exc

        if port in {80 if parsed.scheme.lower() == "http" else 443}:
            port = None
        normalized = f"{parsed.scheme.lower()}://{normalized_host}"
        if port is not None:
            normalized += f":{port}"

        if normalized not in origins:
            origins.append(normalized)

    return origins
