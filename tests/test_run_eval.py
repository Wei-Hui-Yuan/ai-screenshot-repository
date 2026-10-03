import io
import json
from pathlib import Path

import pytest
from google.genai import errors
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from app.schemas import TagResult
from app.tagger import TaggingError, Usage
from eval import run_eval
from eval.run_eval import (
    Config,
    LabelEntry,
    Row,
    cell_verdict,
    classify_query,
    describe_error,
    format_grid,
    is_place_query,
    load_labels,
    parse_args,
    prepare,
    query_fields,
    run,
    same_place,
    score,
    summarise,
    summarise_group,
    words,
)

SECRET = "SECRET-SCREENSHOT-TEXT"


def result(**overrides: object) -> TagResult:
    base: dict[str, object] = {
        "title": "Ramen shop near Shinjuku",
        "summary": "A review of a ramen shop.",
        "category": "food",
        "city": "Tokyo",
        "country": "Japan",
        "tags": ["ramen", "shinjuku"],
        "contains_personal_info": False,
        "extracted_text": "Open 11am to 9pm. Total 1,280 yen",
    }
    return TagResult.model_validate(base | overrides)


def label(**overrides: object) -> LabelEntry:
    base: dict[str, object] = {
        "city": "Tokyo", "country": "Japan", "category": "food", "queries": ["tokyo", "ramen"],
    }
    return LabelEntry.model_validate(base | overrides)


# --- queries -------------------------------------------------------------------


def test_a_query_is_a_word_prefix_match() -> None:
    assert query_fields("tok", result()) == {"place"}
    assert query_fields("kyo", result()) is None  # not an infix match


def test_every_word_must_match_but_in_any_field() -> None:
    assert query_fields("tokyo ramen", result()) == {"place", "title", "summary", "tags"}
    assert query_fields("tokyo kyoto", result()) is None


def test_case_and_punctuation_are_ignored() -> None:
    assert query_fields("RAMEN!", result()) is not None
    assert query_fields("  ", result()) is None
    assert query_fields("???", result()) is None


def test_words_are_split_and_folded_like_the_search_index() -> None:
    assert words("ramen_shop") == ["ramen", "shop"]
    assert words("São Paulo") == ["sao", "paulo"]
    assert words("1,280 yen") == ["1", "280", "yen"]
    assert query_fields("sao", result(city="São Paulo", country="Brazil")) == {"place"}
    assert query_fields("shop", result(title="ramen_shop", summary="Lunch")) == {"title"}


def test_queries_are_classified_by_where_they_matched() -> None:
    r = result(tags=["noodles"], title="Lunch", summary="A meal.", city=None, country=None)

    assert classify_query("noodles", r) == "indexed"
    assert classify_query("1,280", r) == "text-only"
    assert classify_query("sushi", r) == "miss"


# --- scoring -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expected", "found", "same"),
    [(None, None, True), ("Tokyo", " tokyo ", True), ("Tokyo", "Kyoto", False), ("Tokyo", None, False), (None, "Tokyo", False)],
)
def test_same_place(expected: str | None, found: str | None, same: bool) -> None:
    assert same_place(expected, found) is same


def test_a_stated_place_must_match_exactly() -> None:
    assert score(label(), result()).place_ok is True
    assert score(label(), result(city="Kyoto")).place_ok is False
    assert score(label(), result(country=None)).place_ok is False


def test_an_invented_city_counts_against_a_country_only_label() -> None:
    assert score(label(city=None), result(city=None)).place_ok is True
    assert score(label(city=None), result(city="Tokyo")).place_ok is False


def test_an_image_with_no_stated_place_is_judged_on_false_places() -> None:
    no_place = label(city=None, country=None, queries=[])

    assert score(no_place, result(city=None, country=None)).false_place is False
    assert score(no_place, result()).false_place is True
    assert score(no_place, result()).place_ok is None
    assert score(label(), result()).false_place is None


def test_category_and_flag_are_scored_when_labelled() -> None:
    assert score(label(), result()).category_ok is True
    assert score(label(category="travel"), result()).category_ok is False
    assert score(label(), result()).flag_ok is None
    assert score(label(contains_personal_info=True), result()).flag_ok is False
    assert score(label(contains_personal_info=False), result()).flag_ok is True


def test_queries_split_into_place_queries_and_the_rest() -> None:
    s = score(label(queries=["tokyo", "JAPAN", "ramen", "1,280"]), result())

    assert set(s.place_queries) == {"tokyo", "JAPAN"}
    assert s.other_queries == {"ramen": "indexed", "1,280": "text-only"}
    assert is_place_query("Tokyo", label()) and not is_place_query("ramen", label())


def test_text_queries_are_scored_on_their_own() -> None:
    s = score(label(queries=[], text_queries=["1,280", "sushi"]), result())

    assert s.text_queries == {"1,280": "text-only", "sushi": "miss"}
    assert s.place_queries == s.other_queries == {}


def scored_row(
    image: str, lbl: LabelEntry, res: TagResult | None, kind: str | None = None, repeat: int = 0,
    size: str = "1600",
) -> Row:
    row = Row(image=image, size=size, model="m", repeat=repeat, labelled=True,
              usage=Usage(1000, 200, 100, "STOP"), seconds=2.0)
    if res is not None:
        row.result = res.model_dump()
        row.score = score(lbl, res)
    else:
        row.error = {"type": "TaggingError", "kind": kind}
    return row


def test_summary_counts_and_gates() -> None:
    rows = [
        scored_row("a.png", label(), result()),
        scored_row("b.png", label(city=None, country=None, queries=[]), result()),  # invented place
    ]

    s = summarise_group("m", "1600", rows)

    assert (s["place_ok"], s["false_place"], s["category_ok"]) == ("1/1", "1/1", "2/2")
    assert (s["place_queries"], s["other_queries"]) == ("1/1", "1/1")
    assert (s["G1_no_false_place"], s["G2_places_right"], s["G3_place_queries"]) == ("FAIL", "PASS", "PASS")
    assert (s["mean_prompt_tokens"], s["mean_seconds"]) == (1000.0, 2.0)


def test_rate_limits_do_not_count_against_valid_json() -> None:
    rows = [scored_row(f"{i}.png", label(), result()) for i in range(9)]
    rows.append(scored_row("x.png", label(), None, kind="rate_limit"))
    assert summarise_group("m", "1600", rows)["G5_valid_json"] == "PASS"

    rows.append(scored_row("y.png", label(), None, kind="bad_response"))
    assert summarise_group("m", "1600", rows)["G5_valid_json"] == "PASS"  # 9 of 10 attempted is exactly 90%

    rows.append(scored_row("z.png", label(), None, kind="bad_response"))
    assert summarise_group("m", "1600", rows)["G5_valid_json"] == "FAIL"  # 9 of 11


def test_a_cell_that_changes_between_repeats_is_unstable() -> None:
    steady = [scored_row("a.png", label(), result(), repeat=0), scored_row("a.png", label(), result(), repeat=1)]
    assert summarise_group("m", "original", steady)["unstable_cells"] == 0

    wobbly = [scored_row("a.png", label(), result(), repeat=0), scored_row("a.png", label(), result(city="Kyoto"), repeat=1)]
    assert summarise_group("m", "original", wobbly)["unstable_cells"] == 1


def test_g4_needs_every_text_query_found() -> None:
    found = summarise_group("m", "1600", [scored_row("a.png", label(text_queries=["1,280"]), result())])
    missed = summarise_group("m", "1600", [scored_row("a.png", label(text_queries=["sushi"]), result())])

    assert (found["G4_text_queries"], found["text_queries"]) == ("PASS", "1/1")
    assert (missed["G4_text_queries"], missed["text_queries"]) == ("FAIL", "0/1")


def test_g2_fails_if_any_stated_place_is_wrong() -> None:
    one_wrong = [scored_row("a.png", label(), result()), scored_row("b.png", label(), result(city="Kyoto"))]
    all_right = [scored_row("a.png", label(), result()), scored_row("b.png", label(), result())]

    assert summarise_group("m", "1600", one_wrong)["G2_places_right"] == "FAIL"
    assert summarise_group("m", "1600", one_wrong)["place_ok"] == "1/2"
    assert summarise_group("m", "1600", all_right)["G2_places_right"] == "PASS"


@pytest.mark.parametrize(("misses", "verdict"), [(0, "PASS"), (1, "PASS"), (2, "FAIL")])
def test_g3_passes_at_exactly_eighty_percent(misses: int, verdict: str) -> None:
    nothing_about_tokyo = result(city="Kyoto", country="Japan", title="x", summary="y", tags=[], extracted_text="")
    rows = [
        scored_row(f"{i}.png", label(queries=["tokyo"]), nothing_about_tokyo if i < misses else result())
        for i in range(5)
    ]

    assert summarise_group("m", "1600", rows)["G3_place_queries"] == verdict  # 5/5, 4/5, 3/5


@pytest.mark.parametrize("kind", ["rate_limit", "bad_response"])
def test_a_missing_result_makes_the_gates_incomplete_not_passing(kind: str) -> None:
    rows = [scored_row("a.png", label(), result()), scored_row("b.png", label(), None, kind=kind)]

    s = summarise_group("m", "1600", rows)

    assert s["scored"] == "1/2"
    assert [s[g] for g in ("G1_no_false_place", "G2_places_right", "G3_place_queries", "G4_text_queries")] == [
        "INCOMPLETE"
    ] * 4


def test_unlabelled_images_do_not_make_the_gates_incomplete() -> None:
    unlabelled = Row(image="u.png", size="1600", model="m", repeat=0, result=result().model_dump())

    s = summarise_group("m", "1600", [scored_row("a.png", label(), result()), unlabelled])

    assert (s["scored"], s["G2_places_right"]) == ("1/1", "PASS")


def test_without_repeats_stability_is_not_applicable() -> None:
    assert summarise_group("m", "original", [scored_row("a.png", label(), result())])["unstable_cells"] is None


def test_a_rate_limit_is_not_instability() -> None:
    rows = [scored_row("a.png", label(), result(), repeat=0),
            scored_row("a.png", label(), None, kind="rate_limit", repeat=1)]

    assert summarise_group("m", "original", rows)["unstable_cells"] is None


def test_cell_verdicts() -> None:
    unlabelled = Row(image="u.png", size="1600", model="m", repeat=0, result=result().model_dump())
    steady = [scored_row("a.png", label(category="travel"), result(), repeat=r) for r in (0, 1)]
    wobbly = [scored_row("a.png", label(), result(), repeat=0),
              scored_row("a.png", label(), result(city="Kyoto"), repeat=1)]

    assert cell_verdict([]) == "-"
    assert cell_verdict([scored_row("a.png", label(), result())]) == "ok"
    assert cell_verdict([scored_row("a.png", label(), None, kind="bad_response")]) == "ERR:bad_response"
    assert cell_verdict([scored_row("a.png", label(), None, kind="rate_limit")]) == "INCOMPLETE"
    assert cell_verdict([unlabelled]) == "unscored"
    assert cell_verdict(steady) == "category"
    assert cell_verdict(wobbly).startswith("unstable[")


def test_the_grid_shows_what_a_smaller_size_lost_against_the_original() -> None:
    bad = result(city="Kyoto")  # wrong place, and "tokyo" is no longer found
    rows = [
        scored_row("a.png", label(), result(), size="original"),
        scored_row("a.png", label(), result(), size="1600"),
        scored_row("a.png", label(), bad, size="1024"),
        scored_row("b.png", label(), bad, size="original"),  # failed already, so nothing was lost
        scored_row("b.png", label(), bad, size="1600"),
        scored_row("b.png", label(), None, kind="rate_limit", size="1024"),  # unknown, not a loss
    ]

    lines = format_grid(rows)

    assert lines[0] == "Grid for m (ok = every check passed):"
    assert lines[-1] == "  Lost vs original: a.png@1024 [place,q:tokyo]"
    assert any(line.strip().startswith("a.png") and "ok" in line and "place,q:tokyo" in line for line in lines)


def test_a_gate_with_nothing_to_judge_is_not_applicable() -> None:
    s = summarise_group("m", "1600", [scored_row("a.png", label(queries=[]), result())])

    assert (s["G1_no_false_place"], s["G3_place_queries"], s["place_queries"]) == ("n/a", "n/a", "n/a")


# --- labels and images ---------------------------------------------------------


def write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_labels_load_and_allow_null_places(tmp_path: Path) -> None:
    path = write_json(tmp_path / "labels.json", {
        "a.png": {"city": "Tokyo", "country": "Japan", "category": "food", "queries": ["tokyo"]},
        "b.png": {"city": None, "country": None, "category": "other"},
    })

    labels = load_labels(path)

    assert labels["b.png"].city is None
    assert labels["b.png"].queries == []


@pytest.mark.parametrize("entry", [
    {"city": "Tokyo", "country": "Japan", "category": "food", "citty": "typo"},
    {"city": "Tokyo", "country": "Japan", "category": "recipe"},
    {"country": "Japan", "category": "food"},
])
def test_a_bad_label_fails_loudly_and_names_the_image(tmp_path: Path, entry: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="Bad label for a.png"):
        load_labels(write_json(tmp_path / "labels.json", {"a.png": entry}))


def test_a_labels_file_with_a_byte_order_mark_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"a.png": {"city": None, "country": None, "category": "other"}}),
                    encoding="utf-8-sig")  # what some Windows editors write

    assert "a.png" in load_labels(path)


def png_file(folder: Path, name: str, size: tuple[int, int] = (2000, 3000)) -> Path:
    path = folder / name
    Image.linear_gradient("L").resize(size).convert("RGB").save(path, format="PNG")
    return path


def test_original_is_sent_unchanged_and_typed_by_content_not_extension(tmp_path: Path) -> None:
    path = png_file(tmp_path, "really-a-png.jpg")

    data, mime = prepare(path, "original")

    assert data == path.read_bytes()
    assert mime == "image/png"


def test_resized_arms_are_webp_within_the_edge(tmp_path: Path) -> None:
    path = png_file(tmp_path, "a.png")

    for edge in (1600, 1024):
        data, mime = prepare(path, str(edge))
        assert mime == "image/webp"
        assert max(Image.open(io.BytesIO(data)).size) == edge


def test_a_file_that_is_not_an_image_is_rejected(tmp_path: Path) -> None:
    fake = tmp_path / "notes.png"
    fake.write_text("hello")

    with pytest.raises(UnidentifiedImageError):
        prepare(fake, "original")


# --- running -------------------------------------------------------------------


class Recorder:
    """A stand-in for tag_image_with_usage that records what it was asked."""

    def __init__(self, outcome: object | None = None) -> None:
        self.calls: list[tuple[int, str, str | None]] = []
        self.outcome = outcome if outcome is not None else (result(extracted_text=SECRET), Usage(900, 100, 50, "STOP"))

    def __call__(self, data: bytes, mime: str, model: str | None) -> tuple[TagResult, Usage]:
        self.calls.append((len(data), mime, model))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome  # type: ignore[return-value]


class Scripted:
    """Returns or raises each outcome in turn."""

    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, data: bytes, mime: str, model: str | None) -> tuple[TagResult, Usage]:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]


@pytest.fixture
def workspace(tmp_path: Path) -> Config:
    images = tmp_path / "images"
    images.mkdir()
    png_file(images, "a.png")
    png_file(images, "b.png")
    write_json(tmp_path / "labels.json", {
        "a.png": {"city": "Tokyo", "country": "Japan", "category": "food", "queries": ["tokyo"]},
        "b.png": {"city": None, "country": None, "category": "other"},
    })
    return Config(images, tmp_path / "labels.json", ["original", "1600"], ["m1"], 2, 0.5, [], tmp_path / "out", False)


def saved(cfg: Config) -> dict[str, object]:
    (path,) = cfg.out.glob("*.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_image_size_and_repeat_is_run_and_saved(workspace: Config) -> None:
    tag = Recorder()
    pauses: list[float] = []

    rows = run(workspace, tag, pauses.append)

    assert len(rows) == len(tag.calls) == 2 * 2 * 2
    assert {(r.image, r.size, r.repeat) for r in rows} == {
        (image, size, repeat) for image in ("a.png", "b.png") for size in ("original", "1600") for repeat in (0, 1)
    }
    assert {mime for _, mime, _ in tag.calls} == {"image/png", "image/webp"}
    assert {model for _, _, model in tag.calls} == {"m1"}
    assert pauses == [0.5] * 7  # between calls, not after the last
    document = saved(workspace)
    assert len(document["rows"]) == 8  # type: ignore[arg-type]
    assert document["prompt_version"]
    assert rows[0].score is not None and rows[0].bytes_sent and rows[0].usage


def test_screenshot_text_stays_out_of_the_terminal_but_is_saved(workspace: Config, capsys: pytest.CaptureFixture[str]) -> None:
    run(workspace, Recorder(), lambda _: None)

    out = capsys.readouterr().out
    assert SECRET not in out
    assert "Ramen shop near Shinjuku" in out  # title and place are shown
    assert SECRET in json.dumps(saved(workspace))


def test_a_failed_call_is_recorded_without_its_details_and_the_run_goes_on(workspace: Config) -> None:
    cause = ValueError(SECRET)
    usage = Usage(prompt_tokens=1200, thought_tokens=7900, output_tokens=100, finish_reason="MAX_TOKENS")
    failure = TaggingError("bad_response", "MAX_TOKENS", usage)
    failure.__cause__ = cause

    rows = run(workspace, Recorder(failure), lambda _: None)

    assert len(rows) == 8
    assert rows[0].error == {"type": "TaggingError", "kind": "bad_response", "finish_reason": "MAX_TOKENS",
                             "cause_type": "ValueError", "api_code": None, "api_status": None}
    assert rows[0].usage == usage  # the token counts survive the failure, for tuning
    assert SECRET not in json.dumps(saved(workspace))


def test_api_errors_record_only_the_code_and_status() -> None:
    cause = errors.ClientError(429, {"error": {"code": 429, "message": SECRET, "status": "RESOURCE_EXHAUSTED"}})
    failure = TaggingError("rate_limit")
    failure.__cause__ = cause

    info = describe_error(failure)

    assert info["api_code"] == 429 and info["api_status"] == "RESOURCE_EXHAUSTED"
    assert SECRET not in json.dumps(info)


def test_the_run_stops_after_repeated_rate_limits_and_keeps_what_it_has(workspace: Config) -> None:
    tag = Recorder(TaggingError("rate_limit"))

    rows = run(workspace, tag, lambda _: None)

    assert len(rows) == len(tag.calls) == run_eval.MAX_CONSECUTIVE_RATE_LIMITS
    assert len(saved(workspace)["rows"]) == run_eval.MAX_CONSECUTIVE_RATE_LIMITS  # type: ignore[arg-type]


def test_a_real_run_marks_labelled_rows_so_failures_make_its_gates_incomplete(workspace: Config) -> None:
    write_json(workspace.labels, {"a.png": {"city": "Tokyo", "country": "Japan", "category": "food"}})
    ok = (result(), Usage(1, 1, 1, "STOP"))
    tag = Scripted(ok, TaggingError("bad_response"), ok, ok, ok, ok, ok, ok)  # 2nd call: a.png @ original, repeat 1

    rows = run(workspace, tag, lambda _: None)

    assert {r.image: r.labelled for r in rows} == {"a.png": True, "b.png": False}
    s = next(s for s in summarise(rows) if s["size"] == "original")
    assert (s["scored"], s["G2_places_right"]) == ("1/2", "INCOMPLETE")


def test_rate_limits_that_are_not_in_a_row_do_not_stop_the_run(workspace: Config) -> None:
    limited, fine = TaggingError("rate_limit"), (result(), Usage(1, 1, 1, "STOP"))
    tag = Scripted(limited, fine, limited, fine, limited, fine, limited, fine)

    rows = run(workspace, tag, lambda _: None)

    assert len(rows) == tag.calls == 8


def test_a_configuration_error_stops_the_run(workspace: Config) -> None:
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        run(workspace, Recorder(RuntimeError("GEMINI_API_KEY is not set")), lambda _: None)

    assert not workspace.out.exists()


def test_images_without_a_label_are_called_out(workspace: Config, capsys: pytest.CaptureFixture[str]) -> None:
    write_json(workspace.labels, {"a.png": {"city": None, "country": None, "category": "other"}})

    run(workspace, Recorder(), lambda _: None)

    assert "no label for b.png" in capsys.readouterr().out


def test_a_label_without_an_image_is_noted_unless_only_is_used(
    workspace: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    write_json(workspace.labels, {"gone.png": {"city": None, "country": None, "category": "other"}})
    one_size = Config(workspace.images, workspace.labels, ["original"], ["m1"], 1, 0, [], workspace.out, True)
    only = Config(workspace.images, workspace.labels, ["original"], ["m1"], 1, 0, ["a.png"], workspace.out, True)

    run(one_size, Recorder(), lambda _: None)
    assert "gone.png is in the labels" in capsys.readouterr().out

    run(only, Recorder(), lambda _: None)
    assert "gone.png" not in capsys.readouterr().out


def test_only_filters_by_file_name(workspace: Config) -> None:
    tag = Recorder()
    cfg = Config(workspace.images, workspace.labels, ["original"], ["m1"], 1, 0, ["b.png"], workspace.out, False)

    run(cfg, tag, lambda _: None)

    assert len(tag.calls) == 1


def test_a_dry_run_makes_no_calls_and_saves_nothing(workspace: Config, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = Config(workspace.images, workspace.labels, ["original", "1024"], ["m1"], 1, 0, [], workspace.out, True)

    rows = run(cfg, Recorder(RuntimeError("must not be called")), lambda _: None)

    assert rows == []
    assert "bytes" in capsys.readouterr().out
    assert not workspace.out.exists()


def test_without_labels_results_are_saved_unscored(workspace: Config) -> None:
    cfg = Config(workspace.images, workspace.images / "missing.json", ["original"], ["m1"], 1, 0, [],
                 workspace.out, False)

    rows = run(cfg, Recorder(), lambda _: None)

    assert all(r.score is None and r.result for r in rows)


# --- command line --------------------------------------------------------------


def test_defaults_and_model_from_the_environment() -> None:
    cfg = parse_args([], default_model=lambda: "env-model")

    assert cfg.sizes == ["original", "1600", "1024"]
    assert cfg.models == ["env-model"]
    assert (cfg.repeats, cfg.delay, cfg.dry_run) == (1, 5.0, False)


def test_models_can_be_repeated_and_override_the_environment() -> None:
    cfg = parse_args(["--model", "a", "--model", "b", "--only", "x.png"], default_model=lambda: "env-model")

    assert (cfg.models, cfg.only) == (["a", "b"], ["x.png"])


@pytest.mark.parametrize("bad", [["--sizes", "huge"], ["--sizes", ""], ["--repeats", "0"]])
def test_bad_options_are_rejected(bad: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(bad, default_model=lambda: "m")


def test_a_dry_run_needs_no_model() -> None:
    def unset() -> str:
        raise RuntimeError("GEMINI_MODEL is not set")

    assert parse_args(["--dry-run"], default_model=unset).models == ["(unset)"]
    with pytest.raises(RuntimeError):
        parse_args([], default_model=unset)


def test_main_reports_a_bad_labels_file_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, workspace: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(run_eval, "load_dotenv", lambda: None)
    write_json(workspace.labels, {"a.png": {"city": "Tokyo", "country": "Japan", "category": "recipe"}})

    code = run_eval.main(["--images", str(workspace.images), "--labels", str(workspace.labels), "--dry-run"])

    assert code == 1
    assert "Bad label for a.png" in capsys.readouterr().err


def test_main_reports_a_missing_folder_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(run_eval, "load_dotenv", lambda: None)  # never load the real .env in tests

    code = run_eval.main(["--images", str(tmp_path / "nope"), "--dry-run"])

    assert code == 1
    assert "FileNotFoundError" in capsys.readouterr().err
