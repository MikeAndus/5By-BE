from __future__ import annotations

from enum import Enum


class SessionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class RevealedBy(str, Enum):
    QUESTION = "question"
    GUESS = "guess"
    AUTO = "auto"


class EventType(str, Enum):
    QUESTION_ASKED = "question_asked"
    QUESTION_ANSWERED = "question_answered"
    LETTER_GUESSED = "letter_guessed"
    WORD_GUESSED = "word_guessed"


__all__ = ["SessionStatus", "RevealedBy", "EventType"]
