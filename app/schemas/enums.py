import enum


class Topic(str, enum.Enum):
    POLITICS = "Politics"
    SCIENCE = "Science"
    HISTORY = "History"
    ART = "Art"
    CURRENT_AFFAIRS = "Current Affairs"


class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class RevealedBy(str, enum.Enum):
    QUESTION = "question"
    GUESS = "guess"
    AUTO = "auto"


class EventType(str, enum.Enum):
    QUESTION_ASKED = "question_asked"
    QUESTION_ANSWERED = "question_answered"
    LETTER_GUESSED = "letter_guessed"
    WORD_GUESSED = "word_guessed"
