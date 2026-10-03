import json
from collections.abc import Callable, Iterator

import pytest
from google.genai import errors, types

from app import tagger
from app.schemas import CATEGORIES, TagResult
from app.tagger import (
    MAX_OUTPUT_TOKENS,
    MESSAGES,
    REQUEST_TIMEOUT_MS,
    SYSTEM_PROMPT,
    TaggingError,
    Usage,
    tag_image,
    tag_image_with_usage,
)

GOOD = {
    "title": "Ramen shop near Shinjuku",
    "summary": "A review of a ramen shop.",
    "category": "food",
    "city": "Tokyo",
    "country": "Japan",
    "tags": ["ramen", "shinjuku"],
    "contains_personal_info": False,
    "extracted_text": "Open 11am to 9pm",
}
SECRET = "SECRET-SCREENSHOT-TEXT"


@pytest.fixture(autouse=True)
def model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # conftest.py already removes any real key (rule 8).
    monkeypatch.setenv("GEMINI_MODEL", "test-model")


class FakeModels:
    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, object]] = []

    def generate_content(self, *, model: str, contents: list[object], config: types.GenerateContentConfig) -> object:
        self.calls.append({"model": model, "contents": contents, "config": config})
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome: object) -> None:
        self.models = FakeModels(outcome)


@pytest.fixture
def use_fake(monkeypatch: pytest.MonkeyPatch) -> Callable[[object], FakeModels]:
    def install(outcome: object) -> FakeModels:
        client = FakeClient(outcome)
        monkeypatch.setattr(tagger, "_client", lambda: client)
        return client.models

    return install


def reply(
    text: str | None = None,
    finish: types.FinishReason | None = types.FinishReason.STOP,
    *,
    thought: bool = False,
) -> types.GenerateContentResponse:
    parts = [] if text is None else [types.Part(text=text, thought=thought or None)]
    content = types.Content(role="model", parts=parts) if parts else None
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=content, finish_reason=finish)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=1200, thoughts_token_count=300, candidates_token_count=250
        ),
    )


def good_reply() -> types.GenerateContentResponse:
    return reply(json.dumps(GOOD))


def test_returns_a_validated_result_and_usage(use_fake: Callable[[object], FakeModels]) -> None:
    use_fake(good_reply())

    result, usage = tag_image_with_usage(b"img", "image/webp")

    assert result == TagResult.model_validate(GOOD)
    assert usage == Usage(prompt_tokens=1200, thought_tokens=300, output_tokens=250, finish_reason="STOP")
    assert tag_image(b"img", "image/webp") == result


def test_request_is_built_as_planned(use_fake: Callable[[object], FakeModels]) -> None:
    models = use_fake(good_reply())

    tag_image(b"\x89PNG-bytes", "image/png")

    call = models.calls[0]
    config = call["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert call["model"] == "test-model"
    assert config.tools is None  # the model gets no tools (rule 5)
    assert config.automatic_function_calling.disable is True  # type: ignore[union-attr]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == tagger.RESPONSE_SCHEMA
    sent = dict(tagger.RESPONSE_SCHEMA)
    assert sent.pop("propertyOrdering") == list(TagResult.model_fields)
    assert sent == TagResult.model_json_schema()
    assert config.system_instruction == SYSTEM_PROMPT
    assert config.max_output_tokens == MAX_OUTPUT_TOKENS
    image = call["contents"][0]  # type: ignore[index]
    assert image.inline_data.data == b"\x89PNG-bytes"
    assert image.inline_data.mime_type == "image/png"


def test_model_argument_overrides_the_environment(use_fake: Callable[[object], FakeModels]) -> None:
    models = use_fake(good_reply())

    tag_image(b"x", "image/png", model="other-model")

    assert models.calls[0]["model"] == "other-model"


def test_missing_model_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_MODEL")

    with pytest.raises(RuntimeError, match="GEMINI_MODEL"):
        tag_image(b"x", "image/png")


@pytest.fixture
def real_client() -> Iterator[None]:
    tagger._client.cache_clear()
    yield
    tagger._client.cache_clear()


@pytest.mark.usefixtures("real_client")
def test_missing_or_blank_key_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        tagger._client()

    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        tagger._client()


@pytest.mark.usefixtures("real_client")
def test_key_comes_from_gemini_api_key_even_if_google_api_key_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")

    api_client = tagger._client()._api_client

    assert api_client.api_key == "gemini-test-key"
    assert api_client._http_options.timeout == REQUEST_TIMEOUT_MS


def api_error(cls: type[errors.APIError], code: int, status: str) -> errors.APIError:
    return cls(code, {"error": {"code": code, "message": SECRET, "status": status}})


@pytest.mark.parametrize(
    ("failure", "kind"),
    [
        (api_error(errors.ClientError, 429, "RESOURCE_EXHAUSTED"), "rate_limit"),
        (api_error(errors.ClientError, 400, "INVALID_ARGUMENT"), "other"),
        (api_error(errors.ClientError, 404, "NOT_FOUND"), "other"),
        (api_error(errors.ServerError, 503, "UNAVAILABLE"), "other"),
        (TimeoutError(SECRET), "other"),
        (ConnectionError(SECRET), "other"),
    ],
)
def test_a_failed_call_maps_to_a_fixed_kind(
    use_fake: Callable[[object], FakeModels], failure: Exception, kind: str
) -> None:
    use_fake(failure)

    with pytest.raises(TaggingError) as caught:
        tag_image(b"x", "image/png")

    assert caught.value.kind == kind
    assert caught.value.message == MESSAGES[kind]  # type: ignore[index]
    assert SECRET not in str(caught.value)
    assert caught.value.__cause__ is failure


TRUNCATED = json.dumps({**GOOD, "extracted_text": SECRET * 20})[:-25]

BAD_REPLIES = {
    "blocked prompt": (
        types.GenerateContentResponse(
            prompt_feedback=types.GenerateContentResponsePromptFeedback(
                block_reason=types.BlockedReason.PROHIBITED_CONTENT
            )
        ),
        "BLOCKED_PROHIBITED_CONTENT",
    ),
    "safety stop, no content": (reply(None, types.FinishReason.SAFETY), "SAFETY"),
    "sensitive-info stop, no content": (reply(None, types.FinishReason.SPII), "SPII"),
    "thoughts only": (reply("reasoning", thought=True), "STOP"),
    "empty text": (reply(""), "STOP"),
    "cut off at the token limit": (reply(TRUNCATED, types.FinishReason.MAX_TOKENS), "MAX_TOKENS"),
    "not json": (reply("I can't help with that."), "STOP"),
    "missing fields": (reply(json.dumps({"title": "x"})), "STOP"),
    "wrong type": (reply(json.dumps({**GOOD, "contains_personal_info": SECRET})), "STOP"),
}


@pytest.mark.parametrize("name", list(BAD_REPLIES))
def test_an_unusable_reply_is_a_bad_response(use_fake: Callable[[object], FakeModels], name: str) -> None:
    response, finish_reason = BAD_REPLIES[name]
    use_fake(response)

    with pytest.raises(TaggingError) as caught:
        tag_image(b"x", "image/png")

    assert caught.value.kind == "bad_response"
    assert caught.value.finish_reason == finish_reason
    # Neither the error nor its cause may echo text from the screenshot (rule 2).
    assert SECRET not in str(caught.value)
    assert SECRET not in str(caught.value.__cause__)


@pytest.mark.parametrize(
    ("failure", "transient"),
    [
        (api_error(errors.ClientError, 429, "RESOURCE_EXHAUSTED"), True),
        (api_error(errors.ServerError, 503, "UNAVAILABLE"), True),
        (api_error(errors.ServerError, 500, "INTERNAL"), True),
        (api_error(errors.ClientError, 400, "INVALID_ARGUMENT"), False),
        (api_error(errors.ClientError, 404, "NOT_FOUND"), False),
        (TimeoutError(SECRET), False),
    ],
)
def test_only_a_busy_service_is_transient(
    use_fake: Callable[[object], FakeModels], failure: Exception, transient: bool
) -> None:
    use_fake(failure)

    with pytest.raises(TaggingError) as caught:
        tag_image(b"x", "image/png")

    assert caught.value.transient is transient


def quota_error(code: int, retry_delay: str | None) -> errors.APIError:
    details: list[dict[str, object]] = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": []}]
    if retry_delay is not None:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay})
    cls = errors.ClientError if code < 500 else errors.ServerError
    return cls(code, {"error": {"code": code, "message": SECRET, "status": "RESOURCE_EXHAUSTED", "details": details}})


@pytest.mark.parametrize(
    ("failure", "transient"),
    [
        (quota_error(429, "12s"), True),  # a per-minute limit: wait and retry
        (quota_error(429, "30s"), True),
        (quota_error(429, "42034s"), False),  # a daily quota: retrying is futile
        (quota_error(429, "banana"), True),  # an unreadable hint is as unknown as none
        (quota_error(429, None), True),  # no hint: assume it is brief (retries are capped at two)
        (quota_error(503, "5s"), True),
    ],
)
def test_a_long_suggested_wait_is_not_worth_retrying(
    use_fake: Callable[[object], FakeModels], failure: Exception, transient: bool
) -> None:
    use_fake(failure)

    with pytest.raises(TaggingError) as caught:
        tag_image(b"x", "image/png")

    assert caught.value.transient is transient
    assert SECRET not in str(caught.value)


def test_an_unusable_reply_is_not_transient(use_fake: Callable[[object], FakeModels]) -> None:
    use_fake(reply("not json"))

    with pytest.raises(TaggingError) as caught:
        tag_image(b"x", "image/png")

    assert caught.value.transient is False


def test_a_cut_off_reply_reports_its_token_counts(use_fake: Callable[[object], FakeModels]) -> None:
    use_fake(reply(TRUNCATED, types.FinishReason.MAX_TOKENS))

    with pytest.raises(TaggingError) as caught:
        tag_image(b"x", "image/png")

    # The thought tokens are what to look at when tuning max_output_tokens.
    assert caught.value.usage == Usage(1200, 300, 250, "MAX_TOKENS")


def test_a_failed_call_has_no_usage(use_fake: Callable[[object], FakeModels]) -> None:
    use_fake(TimeoutError())

    with pytest.raises(TaggingError) as caught:
        tag_image(b"x", "image/png")

    assert caught.value.usage is None


def test_error_messages_match_the_design_doc() -> None:
    assert MESSAGES == {
        "rate_limit": "Rate limit reached",
        "bad_response": "Unreadable response from Gemini",
        "other": "Tagging error",
    }


def test_the_prompt_names_every_category_in_the_schema() -> None:
    for category in CATEGORIES:
        assert category in SYSTEM_PROMPT


def test_the_prompt_keeps_the_defence_against_text_in_the_image() -> None:
    assert "untrusted" in SYSTEM_PROMPT.lower()
