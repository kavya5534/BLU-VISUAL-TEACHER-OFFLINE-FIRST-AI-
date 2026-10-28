from typing import Literal
from pydantic import BaseModel, Field, field_validator

SceneType = Literal["title_card", "diagram", "code_walkthrough"]

LanguageType = Literal[
    "en", "hi", "ta", "te", "kn", "ml", "bn", "mr", "gu", "es", "fr", "de", "ja"
]

class Scene(BaseModel):
    type: SceneType
    heading: str = Field(min_length=1, max_length=140)
    narration: str = Field(min_length=1, max_length=1200)
    code: str | None = None
    highlight_lines: list[int] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)

    @field_validator("items")
    @classmethod
    def limit_items(cls, value):
        if len(value) > 12:
            raise ValueError("A scene may contain at most 12 items")
        return value

class QuizQuestion(BaseModel):
    id: str | int | None = None
    question: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=6)
    answer: int = Field(ge=0, le=5)
    explanation: str = Field(default="", max_length=600)

class Flashcard(BaseModel):
    id: str | int | None = None
    front: str = Field(min_length=1, max_length=200)
    back: str = Field(min_length=1, max_length=500)
    tip: str | None = Field(default=None, max_length=200)

class Lesson(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    level: Literal["beginner", "intermediate"] = "beginner"
    language: str = "en"
    scenes: list[Scene] = Field(min_length=1, max_length=10)
    quizzes: list[QuizQuestion] = Field(default_factory=list)
    flashcards: list[Flashcard] = Field(default_factory=list)
    category: str = "General"
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None

    @field_validator("scenes")
    @classmethod
    def safe_scene_count(cls, value):
        return value
