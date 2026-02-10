from __future__ import annotations

from dataclasses import dataclass

from app.schemas.enums import Topic

STUB_ANSWERS_BY_LETTER: dict[str, str] = {
    "A": "ATHENS",
    "B": "BERLIN",
    "C": "CARBON",
    "D": "DELHI",
    "E": "EDISON",
    "F": "FALCON",
    "G": "GALILEO",
    "H": "HAMILTON",
    "I": "INDIA",
    "J": "JUPITER",
    "K": "KENYA",
    "L": "LONDON",
    "M": "MERCURY",
    "N": "NEPTUNE",
    "O": "OXYGEN",
    "P": "PYRAMID",
    "Q": "QUEBEC",
    "R": "ROME",
    "S": "SATURN",
    "T": "TOKYO",
    "U": "URANIUM",
    "V": "VENUS",
    "W": "WARSAW",
    "X": "XENON",
    "Y": "YUKON",
    "Z": "ZURICH",
}

_TOPIC_TEMPLATES: dict[Topic, tuple[str, ...]] = {
    Topic.POLITICS: (
        "{topic} (Stub): Name a government-related term that starts with {letter}.",
        "{topic} (Stub): Name a notable public figure whose name starts with {letter}.",
    ),
    Topic.SCIENCE: (
        "{topic} (Stub): Name a famous element that starts with {letter}.",
        "{topic} (Stub): Name a science term that starts with {letter}.",
    ),
    Topic.HISTORY: (
        "{topic} (Stub): Name a historical reference that starts with {letter}.",
        "{topic} (Stub): Name a famous event or era that starts with {letter}.",
    ),
    Topic.ART: (
        "{topic} (Stub): Name an art-related term that starts with {letter}.",
        "{topic} (Stub): Name a famous work or artist that starts with {letter}.",
    ),
    Topic.CURRENT_AFFAIRS: (
        "{topic} (Stub): Name a current-events topic that starts with {letter}.",
        "{topic} (Stub): Name a recent headline concept that starts with {letter}.",
    ),
}


@dataclass(frozen=True)
class StubQuestion:
    question_text: str
    answer: str
    acceptable_variants: list[str]


def generate_stub_question(*, topic: Topic, required_letter: str, cell_index: int) -> StubQuestion:
    letter = required_letter.strip().upper()
    if len(letter) != 1 or letter not in STUB_ANSWERS_BY_LETTER:
        raise ValueError("required_letter must be a single uppercase A-Z letter")

    templates = _TOPIC_TEMPLATES[topic]
    template = templates[cell_index % len(templates)]
    question_text = template.format(topic=topic.value, letter=letter)

    answer = STUB_ANSWERS_BY_LETTER[letter]
    return StubQuestion(
        question_text=question_text,
        answer=answer,
        acceptable_variants=[answer],
    )
