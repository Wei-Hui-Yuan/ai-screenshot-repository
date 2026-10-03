import json

import pytest
from pydantic import ValidationError

from app.schemas import MAX_TAGS, TagResult

# Keys Gemini's response_json_schema accepts, from the description of
# GenerateContentConfig.response_json_schema in google-genai 2.28.0.
GEMINI_SCHEMA_KEYS = {
    "$id", "$defs", "$ref", "$anchor", "type", "format", "title", "description",
    "enum", "items", "prefixItems", "minItems", "maxItems", "minimum", "maximum",
    "anyOf", "oneOf", "properties", "additionalProperties", "required",
    "propertyOrdering",
}


def payload(**overrides: object) -> dict[str, object]:
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
    return base | overrides


def parse(**overrides: object) -> TagResult:
    return TagResult.model_validate(payload(**overrides))


def test_valid_payload_parses() -> None:
    result = parse()

    assert result.title == "Ramen shop near Shinjuku"
    assert result.category == "food"
    assert result.contains_personal_info is False


@pytest.mark.parametrize("raw", ["Travel", "  travel ", "TRAVEL"])
def test_category_is_cleaned(raw: str) -> None:
    assert parse(category=raw).category == "travel"


@pytest.mark.parametrize("raw", ["recipe", "", None, 7, ["travel"]])
def test_unknown_category_becomes_other(raw: object) -> None:
    assert parse(category=raw).category == "other"


def test_tags_are_lowercased_trimmed_and_deduplicated() -> None:
    result = parse(tags=[" Ramen ", "ramen", "TOKYO", "", "  ", "Tokyo", "noodles"])

    assert result.tags == ["ramen", "tokyo", "noodles"]


def test_tags_are_cut_to_the_limit() -> None:
    result = parse(tags=[f"tag{i}" for i in range(MAX_TAGS + 4)])

    assert result.tags == [f"tag{i}" for i in range(MAX_TAGS)]


@pytest.mark.parametrize("bad", ["ramen", [1, 2], None])
def test_tags_that_are_not_a_list_of_strings_are_rejected(bad: object) -> None:
    with pytest.raises(ValidationError):
        parse(tags=bad)


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_blank_place_becomes_none(raw: object) -> None:
    result = parse(city=raw, country=raw)

    assert result.city is None
    assert result.country is None


def test_place_is_trimmed() -> None:
    assert parse(city="  Kyoto ").city == "Kyoto"


@pytest.mark.parametrize("missing", ["title", "city", "contains_personal_info", "extracted_text"])
def test_a_missing_field_is_rejected(missing: str) -> None:
    data = payload()
    del data[missing]

    with pytest.raises(ValidationError):
        TagResult.model_validate(data)


def test_a_wrong_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse(contains_personal_info="SECRET-SCREENSHOT-TEXT")


def test_errors_never_echo_the_input() -> None:
    truncated = json.dumps(payload(extracted_text="SECRET-SCREENSHOT-TEXT " * 20))[:-30]
    wrong_type = json.dumps(payload(contains_personal_info="SECRET-SCREENSHOT-TEXT"))

    for raw in (truncated, wrong_type):
        with pytest.raises(ValidationError) as caught:
            TagResult.model_validate_json(raw)
        assert "SECRET" not in str(caught.value)


def test_extracted_text_is_last_so_truncation_keeps_the_flag() -> None:
    fields = list(TagResult.model_fields)

    assert fields[-1] == "extracted_text"
    assert fields.index("contains_personal_info") < fields.index("extracted_text")


def _schema_keys(node: object) -> set[str]:
    """Keyword names used in a JSON schema, skipping field names under `properties`."""
    if isinstance(node, list):
        return set().union(*(_schema_keys(item) for item in node)) if node else set()
    if not isinstance(node, dict):
        return set()
    keys = set(node)
    for name, child in node.items():
        if name == "properties":
            keys |= set().union(*(_schema_keys(c) for c in child.values()))
        elif name == "$defs":
            keys |= set().union(*(_schema_keys(c) for c in child.values()))
        else:
            keys |= _schema_keys(child)
    return keys


def test_json_schema_uses_only_keys_gemini_supports() -> None:
    used = _schema_keys(TagResult.model_json_schema())

    assert used <= GEMINI_SCHEMA_KEYS, used - GEMINI_SCHEMA_KEYS
