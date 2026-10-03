"""Shared test helpers: sample images and a stand-in for the Gemini tagger."""

import io
from collections.abc import Callable

from PIL import Image

from app.schemas import TagResult


def png_bytes(colour: str = "steelblue", size: tuple[int, int] = (120, 80)) -> bytes:
    """A small valid PNG. A different colour gives a different file hash."""
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, format="PNG")
    return out.getvalue()


def good_result(**overrides: object) -> TagResult:
    base: dict[str, object] = {
        "title": "Ramen shop near Shinjuku",
        "summary": "A review of a ramen shop.",
        "category": "food",
        "city": "Tokyo",
        "country": "Japan",
        "tags": ["ramen", "shinjuku"],
        "contains_personal_info": False,
        "extracted_text": "Open 11am to 9pm",
    }
    return TagResult.model_validate(base | overrides)


class InlineExecutor:
    """Stands in for the tagging pool: runs each task at once, so a request returns
    only after its tagging is done and the tests stay deterministic."""

    def submit(self, fn: Callable[..., object], *args: object) -> None:
        fn(*args)

    def shutdown(self, *args: object, **kwargs: object) -> None:
        """The app shuts its pool down when it stops; there is nothing to stop here."""


class FakeTagger:
    """Stands in for app.tagger.tag_image. Each call returns or raises the next
    outcome; the last one repeats. An outcome can be a function, to run a side
    effect first."""

    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes) or [good_result()]
        self.calls = 0

    def __call__(self, data: bytes, mime_type: str, model: str | None = None) -> TagResult:
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if callable(outcome):
            outcome = outcome()
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, TagResult)
        return outcome


Outcome = TagResult | Exception | Callable[[], TagResult]
