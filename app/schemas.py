"""Pydantic models. TagResult is the shape Gemini must return, and the only form
its output takes before it reaches the database (hard rule 5)."""

from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal["travel", "food", "article", "receipt", "other"]
CATEGORIES: tuple[str, ...] = get_args(Category)
MAX_TAGS = 8


class TagResult(BaseModel):
    # A validation error echoes part of its input by default, and here the input
    # is text from a screenshot. Hide it so it can't reach a log or the UI (rule 2).
    model_config = ConfigDict(hide_input_in_errors=True, str_strip_whitespace=True)

    # Field order is the order we ask Gemini to write them in (propertyOrdering in
    # tagger.py). If a long reply is cut off, it should lose the end of
    # extracted_text, not the personal-info flag. The spike checks that it holds.
    title: str
    summary: str
    category: Category
    city: str | None
    country: str | None
    # No defaults and no maxLength: Gemini's response schema doesn't support them.
    # maxItems is supported, and the validator below cuts to 8 if it's ignored.
    tags: list[str] = Field(max_length=MAX_TAGS)
    contains_personal_info: bool
    extracted_text: str

    @field_validator("category", mode="before")
    @classmethod
    def _unknown_category_is_other(cls, value: object) -> object:
        cleaned = value.strip().lower() if isinstance(value, str) else value
        return cleaned if cleaned in CATEGORIES else "other"

    @field_validator("tags", mode="before")
    @classmethod
    def _normalise_tags(cls, value: object) -> object:
        if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
            return value  # not a list of strings: let normal validation reject it
        cleaned = (tag.strip().lower() for tag in value)
        unique = dict.fromkeys(tag for tag in cleaned if tag)  # keeps first-seen order
        return list(unique)[:MAX_TAGS]

    @field_validator("city", "country", mode="before")
    @classmethod
    def _blank_place_is_none(cls, value: object) -> object:
        return (value.strip() or None) if isinstance(value, str) else value
