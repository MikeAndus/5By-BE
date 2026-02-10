from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Provide a default URL for import-time settings validation in tests.
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgres://postgres:postgres@localhost:5432/fiveby_test"),
)

from app.api.routes import health as health_route
from app.core.config import get_settings
from app.db.session import get_async_engine, get_async_sessionmaker
from app.main import create_app


def _build_client() -> TestClient:
    get_settings.cache_clear()
    get_async_engine.cache_clear()
    get_async_sessionmaker.cache_clear()
    return TestClient(create_app())


def test_health_returns_ok() -> None:
    with _build_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "five-by-backend"
    assert "X-Request-ID" in response.headers


def test_health_with_db_zero_does_not_ping_database(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"value": False}

    async def fake_db_ping(_session: object) -> bool:
        called["value"] = True
        return True

    monkeypatch.setattr(health_route, "db_ping", fake_db_ping)

    with _build_client() as client:
        response = client.get("/health?db=0")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert called["value"] is False


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_health_with_db_one_when_database_available() -> None:
    with _build_client() as client:
        response = client.get("/health?db=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["db"]["checked"] is True
    assert payload["db"]["ok"] is True
