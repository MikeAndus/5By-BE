from __future__ import annotations

import json
from typing import Annotated, Any
import uuid

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import TopicDbEnum
from app.db.models.openai_response_log import OpenAiResponseLog
from app.schemas.enums import Topic
from app.services.openai_client import OpenAIClientUnavailableError, get_openai_client

MODEL_NAME = "gpt-5-mini"
MAX_ATTEMPTS = 3


class OpenAiQuestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_text: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    acceptable_variants: list[Annotated[str, StringConstraints(min_length=1)]] = Field(min_length=1)


class OpenAiGenerationFailedError(RuntimeError):
    pass


_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["question_text", "answer", "acceptable_variants"],
    "properties": {
        "question_text": {"type": "string"},
        "answer": {"type": "string"},
        "acceptable_variants": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
        },
    },
}

_DEVELOPER_PROMPT = "\n".join(
    [
        "You generate one trivia question as strict JSON only.",
        "Rules:",
        "- Keep it common-knowledge and unambiguous.",
        "- The correct answer must start with the required letter.",
        "- Include acceptable_variants for strict exact matching.",
        "- Do not add any keys beyond question_text, answer, acceptable_variants.",
        "- Keep question_text concise.",
    ]
)


def _build_user_prompt(*, topic: Topic, required_letter: str, prior_questions: list[str]) -> str:
    prior_lines = "\n".join(f"- {question}" for question in prior_questions) or "- (none)"
    return "\n".join(
        [
            f"Topic: {topic.value}",
            f"Required starting letter for answer: {required_letter}",
            "Prior question_text values for this session/player/cell (avoid repetition):",
            prior_lines,
            "Return JSON only.",
        ]
    )


def _response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        payload = response.model_dump(mode="json")
        if isinstance(payload, dict):
            return payload

    if isinstance(response, dict):
        return response

    return {"value": str(response)}


def _extract_structured_payload(response: Any, response_payload: dict[str, Any]) -> dict[str, Any]:
    output_parsed = getattr(response, "output_parsed", None)
    if isinstance(output_parsed, dict):
        return output_parsed

    if isinstance(response_payload.get("output_parsed"), dict):
        return response_payload["output_parsed"]

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        parsed = json.loads(output_text)
        if isinstance(parsed, dict):
            return parsed

    payload_output_text = response_payload.get("output_text")
    if isinstance(payload_output_text, str) and payload_output_text.strip():
        parsed = json.loads(payload_output_text)
        if isinstance(parsed, dict):
            return parsed

    output_items = response_payload.get("output")
    if isinstance(output_items, list):
        for output_item in output_items:
            if not isinstance(output_item, dict):
                continue
            content_items = output_item.get("content")
            if not isinstance(content_items, list):
                continue
            for content in content_items:
                if not isinstance(content, dict):
                    continue

                if isinstance(content.get("json"), dict):
                    return content["json"]

                text_value = content.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    parsed = json.loads(text_value)
                    if isinstance(parsed, dict):
                        return parsed

    raise ValueError("OpenAI response did not contain parseable structured JSON")


def _semantic_guard_error(*, parsed: OpenAiQuestionPayload, required_letter: str) -> str | None:
    answer = parsed.answer.strip()
    required = required_letter.strip().casefold()
    normalized_variants = [variant.strip() for variant in parsed.acceptable_variants]

    if len(parsed.question_text) > 500:
        return "question_too_long"

    if not parsed.acceptable_variants:
        return "acceptable_variants_empty"

    if any(not variant for variant in normalized_variants):
        return "acceptable_variant_empty_after_trim"

    if not answer:
        return "answer_empty_after_trim"

    if not answer.casefold().startswith(required):
        return "answer_does_not_start_with_required_letter"

    return None


async def generate_openai_question(
    *,
    session_id: uuid.UUID,
    player_number: int,
    cell_index: int,
    topic: Topic,
    required_letter: str,
    prior_questions: list[str],
    db: AsyncSession,
) -> tuple[dict[str, Any], OpenAiResponseLog]:
    client = get_openai_client()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        request_payload: dict[str, Any] = {
            "model": MODEL_NAME,
            "input": [
                {"role": "developer", "content": _DEVELOPER_PROMPT},
                {
                    "role": "user",
                    "content": _build_user_prompt(
                        topic=topic,
                        required_letter=required_letter,
                        prior_questions=prior_questions,
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "trivia_question",
                    "strict": True,
                    "schema": _RESPONSE_SCHEMA,
                }
            },
        }

        log_row = OpenAiResponseLog(
            session_id=session_id,
            player_number=player_number,
            cell_index=cell_index,
            topic=TopicDbEnum[topic.name],
            attempt=attempt,
            model=MODEL_NAME,
            request_payload=request_payload,
            response_payload=None,
            parsed_payload=None,
            error_message=None,
            event_log_id=None,
        )
        db.add(log_row)
        await db.flush()

        try:
            response = await client.responses.create(**request_payload)
        except OpenAIClientUnavailableError:
            raise
        except Exception as exc:
            error_response = getattr(exc, "response", None)
            if error_response is not None:
                response_body = getattr(error_response, "text", None)
                if isinstance(response_body, str) and response_body:
                    log_row.response_payload = {"error_response": response_body}
            log_row.error_message = f"openai_request_failed: {exc}"
            continue

        response_payload = _response_to_dict(response)
        log_row.response_payload = response_payload

        try:
            parsed_payload_raw = _extract_structured_payload(response, response_payload)
            parsed_payload = OpenAiQuestionPayload.model_validate(parsed_payload_raw)
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            log_row.error_message = f"structured_output_parse_failed: {exc}"
            continue

        semantic_error = _semantic_guard_error(parsed=parsed_payload, required_letter=required_letter)
        if semantic_error is not None:
            log_row.parsed_payload = parsed_payload.model_dump(mode="json")
            log_row.error_message = semantic_error
            continue

        parsed_output = parsed_payload.model_dump(mode="json")
        log_row.parsed_payload = parsed_output
        return parsed_output, log_row

    raise OpenAiGenerationFailedError("OpenAI generation attempts exhausted")
