from __future__ import annotations

from enum import Enum


class Topic(str, Enum):
    POLITICS = "Politics"
    SCIENCE = "Science"
    HISTORY = "History"
    ART = "Art"
    CURRENT_AFFAIRS = "Current Affairs"


class Direction(str, Enum):
    ACROSS = "across"
    DOWN = "down"


class SessionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class RevealedBy(str, Enum):
    QUESTION = "question"
    GUESS = "guess"
    AUTO = "auto"


TOPIC_VALUES = {member.value for member in Topic}


__all__ = [
    "Direction",
    "RevealedBy",
    "SessionStatus",
    "TOPIC_VALUES",
    "Topic",
]
