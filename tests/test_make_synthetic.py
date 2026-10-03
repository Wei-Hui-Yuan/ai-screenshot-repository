import json
from pathlib import Path

import pytest
from PIL import Image

from eval.make_synthetic import HEIGHT, SPECS, WIDTH, Spec, generate, render
from eval.run_eval import LabelEntry, words


def spec_words(spec: Spec) -> list[str]:
    return words(" ".join([spec.header] + [text for _, text in spec.blocks]))


def test_it_writes_phone_sized_screenshots_and_matching_labels(tmp_path: Path) -> None:
    paths = generate(tmp_path)

    assert len(paths) == len(SPECS) == 6
    for path in paths:
        with Image.open(path) as image:
            assert (image.format, image.size) == ("PNG", (WIDTH, HEIGHT))
    labels = json.loads((tmp_path / "labels.json").read_text(encoding="utf-8"))
    assert set(labels) == {p.name for p in paths}


def test_every_label_is_valid_for_the_harness(tmp_path: Path) -> None:
    generate(tmp_path)
    labels = json.loads((tmp_path / "labels.json").read_text(encoding="utf-8"))

    for entry in labels.values():
        LabelEntry.model_validate(entry)


def test_output_is_deterministic(tmp_path: Path) -> None:
    first = [p.read_bytes() for p in generate(tmp_path / "a")]
    second = [p.read_bytes() for p in generate(tmp_path / "b")]

    assert first == second


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name)
def test_text_is_drawn_and_fits_on_the_screen(spec: Spec) -> None:
    image = render(spec).convert("L")
    dark = image.point(lambda v: 255 if v < 100 else 0)

    assert dark.crop((0, 300, WIDTH, HEIGHT)).getbbox() is not None  # ink below the header
    assert dark.crop((0, HEIGHT - 150, WIDTH, HEIGHT)).getbbox() is None  # nothing near the bottom edge
    assert dark.crop((WIDTH - 30, 300, WIDTH, HEIGHT)).getbbox() is None  # nothing clipped at the right


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name)
def test_every_query_is_actually_on_the_screenshot(spec: Spec) -> None:
    on_screen = spec_words(spec)

    for query in list(spec.label["queries"]) + list(spec.label["text_queries"]):  # type: ignore[call-overload]
        assert all(any(w.startswith(term) for w in on_screen) for term in words(query)), query


def test_the_set_covers_the_cases_it_exists_for() -> None:
    labels = {s.name: s.label for s in SPECS}
    no_place = [n for n, e in labels.items() if e["city"] is None and e["country"] is None]
    flagged = [n for n, e in labels.items() if e["contains_personal_info"]]
    injection = next(s for s in SPECS if s.name == "note-injection")

    assert labels["travel-kyoto"]["city"] == "Kyoto"
    assert len(no_place) == 5  # AC-5
    assert flagged == ["form-personal"]  # AC-8
    assert "ignore all previous instructions" in " ".join(t for _, t in injection.blocks).lower()
    assert injection.label["city"] is None and injection.label["country"] is None  # obeying it would show up as a false place
    assert any(e["text_queries"] for e in labels.values())  # AC-4
