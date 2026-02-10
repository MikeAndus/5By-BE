from pydantic import ValidationError

from app.schemas.answer_question import AnswerQuestionRequest, QuestionAnsweredEventData
from app.schemas.enums import Topic


def test_answer_question_request_trims_answer() -> None:
    payload = AnswerQuestionRequest(player_number=1, answer="  Mercury  ")
    assert payload.answer == "Mercury"


def test_question_answered_event_requires_revealed_letter_for_correct_answer() -> None:
    try:
        QuestionAnsweredEventData(
            cell_index=0,
            row=0,
            col=0,
            topic=Topic.SCIENCE,
            answer="Mercury",
            correct=True,
            revealed_letter=None,
            lock_cleared_cell_index=None,
        )
    except ValidationError:
        return

    raise AssertionError("Expected ValidationError when correct=true and revealed_letter is null")


def test_question_answered_event_forbids_revealed_letter_when_incorrect() -> None:
    try:
        QuestionAnsweredEventData(
            cell_index=0,
            row=0,
            col=0,
            topic=Topic.SCIENCE,
            answer="wrong",
            correct=False,
            revealed_letter="M",
            lock_cleared_cell_index=None,
        )
    except ValidationError:
        return

    raise AssertionError("Expected ValidationError when correct=false and revealed_letter is present")
