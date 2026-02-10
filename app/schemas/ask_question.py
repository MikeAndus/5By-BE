from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.enums import Topic

NonEmptyString = Annotated[str, StringConstraints(min_length=1)]


class AskQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_number: Literal[1, 2]
    cell_index: int = Field(ge=0, le=24)
    topic: Topic


class QuestionAskedEventData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_index: int = Field(ge=0, le=24)
    row: int = Field(ge=0, le=4)
    col: int = Field(ge=0, le=4)
    topic: Topic
    question_text: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1)
    acceptable_variants: list[NonEmptyString] = Field(min_length=1)
    generator: Literal["stub_v1"]
