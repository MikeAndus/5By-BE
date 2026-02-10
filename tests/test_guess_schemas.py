from pydantic import ValidationError

from app.schemas.enums import GuessDirection
from app.schemas.guess_letter import GuessLetterRequest, LetterGuessedEventData
from app.schemas.guess_word import GuessWordRequest, WordGuessedEventData


def test_guess_letter_request_forbids_unknown_fields() -> None:
    try:
        GuessLetterRequest(player_number=1, cell_index=12, letter="m", extra_field=True)
    except ValidationError:
        return

    raise AssertionError("Expected ValidationError for unknown field")


def test_guess_word_request_accepts_contract_values() -> None:
    payload = GuessWordRequest(
        player_number=2,
        direction=GuessDirection.ACROSS,
        index=3,
        word="stock",
    )
    assert payload.direction == GuessDirection.ACROSS
    assert payload.word == "stock"


def test_letter_guessed_event_requires_lock_shape_for_incorrect_guess() -> None:
    try:
        LetterGuessedEventData(
            cell_index=8,
            row=1,
            col=3,
            guessed_letter="Z",
            correct=False,
            revealed_letter=None,
            score_delta=-5,
            opponent_score_delta=1,
            locks_enqueued=[],
            auto_reveals=[],
        )
    except ValidationError:
        return

    raise AssertionError("Expected ValidationError when incorrect guess omits cell lock index")


def test_word_guessed_event_requires_sorted_locks() -> None:
    try:
        WordGuessedEventData(
            direction=GuessDirection.DOWN,
            index=0,
            guessed_word="WRONG",
            correct=False,
            revealed_cells=[],
            score_delta=-5,
            opponent_score_delta=1,
            locks_enqueued=[10, 0, 5],
            auto_reveals=[],
        )
    except ValidationError:
        return

    raise AssertionError("Expected ValidationError when locks_enqueued is not sorted")
