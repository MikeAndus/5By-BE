from __future__ import annotations

import json
import uuid

import pytest

from app.schemas.enums import Topic
from app.services import trivia_generator_openai


class _FakeDb:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return None


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.output_text = json.dumps(payload)

    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return {"output_text": self.output_text}


class _FakeResponses:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self._payloads = payloads

    async def create(self, **kwargs):  # noqa: ANN003
        payload = self._payloads.pop(0)
        return _FakeResponse(payload)


class _FakeClient:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.responses = _FakeResponses(payloads)


@pytest.mark.asyncio
async def test_generate_openai_question_retries_and_logs_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeClient(
        [
            {
                "question_text": "Science question",
                "answer": "Berlin",
                "acceptable_variants": ["Berlin"],
            },
            {
                "question_text": "Name a planet starting with M",
                "answer": "Mercury",
                "acceptable_variants": ["Mercury", "mercury"],
            },
        ]
    )
    monkeypatch.setattr(trivia_generator_openai, "get_openai_client", lambda: fake_client)

    db = _FakeDb()
    payload, successful_attempt = await trivia_generator_openai.generate_openai_question(
        session_id=uuid.uuid4(),
        player_number=1,
        cell_index=7,
        topic=Topic.SCIENCE,
        required_letter="M",
        prior_questions=[],
        db=db,
    )

    assert payload["answer"] == "Mercury"
    assert successful_attempt.attempt == 2
    assert len(db.rows) == 2

    first_attempt = db.rows[0]
    second_attempt = db.rows[1]

    assert getattr(first_attempt, "attempt") == 1
    assert getattr(first_attempt, "error_message") == "answer_does_not_start_with_required_letter"
    assert getattr(second_attempt, "attempt") == 2
    assert getattr(second_attempt, "error_message") is None
    assert getattr(second_attempt, "parsed_payload") is not None
