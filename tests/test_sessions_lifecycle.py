from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable
from typing import TypeVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

# Provide a default URL for import-time settings validation in tests.
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgres://postgres:postgres@localhost:5432/fiveby_test"),
)

from app.api.routes import sessions as sessions_route
from app.core.config import get_settings
from app.db.models import CellState, Grid, Session
from app.db.session import get_async_engine, get_async_sessionmaker
from app.main import create_app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
T = TypeVar("T")


def _build_client() -> TestClient:
    get_settings.cache_clear()
    get_async_engine.cache_clear()
    get_async_sessionmaker.cache_clear()
    return TestClient(create_app())


def _run(coro: Awaitable[T]) -> T:
    return asyncio.run(coro)


def _grid_cells(seed: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(alphabet[(seed + offset) % 26] for offset in range(25))


async def _ensure_seeded_grids(minimum_count: int = 2) -> None:
    session_factory = get_async_sessionmaker()
    async with session_factory() as db:
        count_result = await db.execute(select(func.count(Grid.grid_id)))
        total = int(count_result.scalar_one())
        seed = 0

        while total < minimum_count:
            candidate = _grid_cells(seed)
            seed += 1
            existing = await db.execute(select(Grid.grid_id).where(Grid.cells == candidate))
            if existing.scalar_one_or_none() is not None:
                continue

            words = [candidate[index : index + 5] for index in range(0, 25, 5)]
            db.add(
                Grid(
                    cells=candidate,
                    words_across=words,
                    words_down=words,
                )
            )
            total += 1

        await db.commit()


async def _load_session_row_and_cells(session_id: str) -> tuple[Session, list[CellState]]:
    parsed_session_id = uuid.UUID(session_id)
    session_factory = get_async_sessionmaker()
    async with session_factory() as db:
        session_result = await db.execute(select(Session).where(Session.session_id == parsed_session_id))
        session_row = session_result.scalar_one()

        cell_states_result = await db.execute(
            select(CellState)
            .where(CellState.session_id == parsed_session_id)
            .order_by(CellState.player_id.asc(), CellState.cell_index.asc())
        )
        cell_states = list(cell_states_result.scalars().all())

    return session_row, cell_states


async def _delete_session(session_id: str) -> None:
    parsed_session_id = uuid.UUID(session_id)
    session_factory = get_async_sessionmaker()
    async with session_factory() as db:
        await db.execute(delete(Session).where(Session.session_id == parsed_session_id))
        await db.commit()


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")
def test_create_session_initializes_state() -> None:
    _run(_ensure_seeded_grids())

    session_id: str | None = None
    with _build_client() as client:
        response = client.post(
            "/sessions",
            json={"player_1_name": "  Avery  ", "player_2_name": "   "},
        )

    assert response.status_code == 201
    payload = response.json()
    session_id = payload["session_id"]

    assert payload["status"] == "in_progress"
    assert payload["current_turn"] == 1
    assert payload["last_event"]["type"] == "session_created"
    assert payload["last_event"]["result"] == "ok"
    assert [player["player_number"] for player in payload["players"]] == [1, 2]

    player_1 = payload["players"][0]
    player_2 = payload["players"][1]
    assert player_1["name"] == "Avery"
    assert player_2["name"] is None
    assert player_1["grid_id"] != player_2["grid_id"]
    assert player_1["score"] == 100
    assert player_2["score"] == 100
    assert player_1["completed"] is False
    assert player_2["completed"] is False

    for player in payload["players"]:
        assert [cell["index"] for cell in player["cells"]] == list(range(25))
        for cell in player["cells"]:
            assert cell["revealed"] is False
            assert "letter" not in cell
            assert cell["locked"] is False
            assert cell["topics_used"] == []
            assert cell["revealed_by"] is None

    session_row, cell_states = _run(_load_session_row_and_cells(session_id))
    assert session_row.current_turn == 1
    assert session_row.status.value == "in_progress"
    assert session_row.player_1_score == 100
    assert session_row.player_2_score == 100
    assert len(cell_states) == 50
    assert len([cell for cell in cell_states if cell.player_id == 1]) == 25
    assert len([cell for cell in cell_states if cell.player_id == 2]) == 25
    for state in cell_states:
        assert state.revealed is False
        assert state.locked is False
        assert state.topics_used == []
        assert state.revealed_by is None

    assert session_id is not None
    _run(_delete_session(session_id))


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")
def test_get_session_returns_snapshot() -> None:
    _run(_ensure_seeded_grids())

    session_id: str | None = None
    with _build_client() as client:
        create_response = client.post("/sessions", json={})

        assert create_response.status_code == 201
        session_id = create_response.json()["session_id"]

        response_1 = client.get(f"/sessions/{session_id}")
        response_2 = client.get(f"/sessions/{session_id}")

    assert response_1.status_code == 200
    assert response_2.status_code == 200
    payload_1 = response_1.json()
    payload_2 = response_2.json()

    assert payload_1 == payload_2
    assert payload_1["last_event"]["type"] == "none"
    assert [player["player_number"] for player in payload_1["players"]] == [1, 2]
    assert [cell["index"] for cell in payload_1["players"][0]["cells"]] == list(range(25))
    assert [cell["index"] for cell in payload_1["players"][1]["cells"]] == list(range(25))

    assert session_id is not None
    _run(_delete_session(session_id))


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")
def test_get_session_404() -> None:
    with _build_client() as client:
        response = client.get(f"/sessions/{uuid.uuid4()}")

    assert response.status_code == 404


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")
def test_post_sessions_requires_seeded_grids(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_select_two_random_grids(_db: object) -> list[Grid]:
        return []

    monkeypatch.setattr(sessions_route, "_select_two_random_grids", fake_select_two_random_grids)

    with _build_client() as client:
        response = client.post("/sessions", json={})

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Not enough grids seeded to create a session."
