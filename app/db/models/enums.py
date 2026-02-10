from __future__ import annotations

from enum import Enum




class RevealedBy(str, Enum):
    QUESTION = "question"
    GUESS = "guess"
    AUTO = "auto"


class EventType(str, Enum):
    QUESTION_ASKED = "question_asked"
    QUESTION_ANSWERED = "question_answered"
    LETTER_GUESSED = "letter_guessed"
    WORD_GUESSED = "word_guessed"

class SessionStatus(str, Enum):
    LOBBY = "lobby"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


__all__ = ["SessionStatus", "RevealedBy", "EventType"]
