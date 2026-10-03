import io
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import db, images, main
from app.tagger import TaggingError
from helpers import FakeTagger, InlineExecutor, good_result, png_bytes

SECRET = "SECRET-SCREENSHOT-TEXT"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    monkeypatch.setattr(main, "RETRY_WAITS", (0, 0))  # no real waiting in tests
    with TestClient(main.app) as test_client:
        monkeypatch.setattr(main, "tagging_pool", InlineExecutor())  # after startup made the real pool
        yield test_client


def use(monkeypatch: pytest.MonkeyPatch, *outcomes: object) -> FakeTagger:
    tagger = FakeTagger(*outcomes)
    monkeypatch.setattr(main, "tag_image", tagger)  # the seam: tests never reach Gemini (rule 8)
    return tagger


def post(client: TestClient, *blobs: bytes, names: list[str] | None = None):  # noqa: ANN201
    files = [("files", ((names or [])[i] if names else f"shot{i}.png", blob, "image/png"))
             for i, blob in enumerate(blobs)]
    return client.post("/api/images", files=files)


def one(client: TestClient, image_id: int) -> dict[str, object]:
    response = client.get(f"/api/images/{image_id}")
    assert response.status_code == 200
    return response.json()


def titles(client: TestClient, **params: object) -> list[str]:
    return [r["title"] for r in client.get("/api/images", params=params).json()]


# --- upload (AC-1, AC-2, AC-6) -------------------------------------------------


def test_an_upload_is_pending_then_tagged_with_the_model_and_prompt_recorded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use(monkeypatch)

    response = post(client, png_bytes())

    assert response.json() == [{"id": 1, "status": "pending", "duplicate": False, "error": None}]
    row = one(client, 1)
    assert (row["status"], row["title"], row["city"], row["model"], row["prompt_version"]) == (
        "tagged", "Ramen shop near Shinjuku", "Tokyo", "test-model", "v1")


def test_five_uploads_all_end_up_tagged_and_none_stay_pending(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-1
    use(monkeypatch)

    results = post(client, *[png_bytes(c) for c in ("red", "green", "blue", "black", "white")]).json()

    assert [r["id"] for r in results] == [1, 2, 3, 4, 5]
    assert {r["status"] for r in client.get("/api/images").json()} == {"tagged"}
    assert client.get("/api/images", params={"status": "pending"}).json() == []


def test_the_same_file_twice_is_one_row_and_one_gemini_call(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-2, J7
    tagger = use(monkeypatch)
    data = png_bytes()

    first = post(client, data).json()[0]
    again = post(client, data).json()[0]
    inside_one_request = post(client, png_bytes("red"), png_bytes("red")).json()

    assert again == {"id": first["id"], "status": "tagged", "duplicate": True, "error": None}
    assert inside_one_request[1]["duplicate"] is True and inside_one_request[0]["id"] == inside_one_request[1]["id"]
    assert tagger.calls == 2  # one per distinct file
    assert len(client.get("/api/images").json()) == 2


def test_bad_files_are_rejected_with_a_fixed_message_and_nothing_is_saved(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-6, J4
    tagger = use(monkeypatch)
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    whole = png_bytes(size=(200, 200))

    results = post(client, b"just some text", gif.getvalue(), b"\0" * (images.MAX_BYTES + 1), whole[:60]).json()

    assert [r["error"] for r in results] == [
        "not PNG, JPEG or WebP", "not PNG, JPEG or WebP", "over 10 MB", "unreadable image"]
    assert all(r["id"] is None for r in results)
    assert client.get("/api/images").json() == [] and tagger.calls == 0
    assert list(db.images_dir().iterdir()) == []


def test_one_bad_file_does_not_stop_the_others_and_results_keep_the_order_sent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use(monkeypatch)

    results = post(client, png_bytes("red"), b"nope", png_bytes("blue")).json()

    assert [(r["id"], r["error"]) for r in results] == [(1, None), (None, "not PNG, JPEG or WebP"), (2, None)]


def test_more_than_twenty_files_are_refused(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    tagger = use(monkeypatch)

    response = post(client, *[png_bytes(size=(10 + i, 10)) for i in range(21)])

    assert response.status_code == 400 and "20" in response.json()["detail"]
    assert tagger.calls == 0 and client.get("/api/images").json() == []


def test_the_uploaded_name_is_never_used_the_stored_name_is_the_hash(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # rule 3
    use(monkeypatch)
    data = png_bytes()

    post(client, data, names=["../../evil.png"])

    assert [p.name for p in db.images_dir().iterdir()] == [f"{images.sha256(data)}.webp"]
    assert list(db.data_dir().parent.rglob("*evil*")) == []  # nothing anywhere carries that name


def test_stored_images_are_small_webp_and_the_original_is_not_kept(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-13 through the app
    use(monkeypatch)
    big = io.BytesIO()
    Image.new("RGB", (3000, 2000), "tomato").save(big, format="PNG")

    post(client, big.getvalue())

    stored = client.get("/api/images/1/file")
    image = Image.open(io.BytesIO(stored.content))
    assert stored.headers["content-type"] == "image/webp"
    assert (image.format, max(image.size)) == ("WEBP", 1600)
    assert len(image.getexif()) == 0


def test_the_api_never_exposes_the_hash_or_the_stored_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use(monkeypatch)
    post(client, png_bytes())

    for body in (one(client, 1), client.get("/api/images").json()[0]):
        assert "sha256" not in body and "file_path" not in body
    assert "extracted_text" in one(client, 1)
    assert "extracted_text" not in client.get("/api/images").json()[0]  # the list stays light


# --- failures and retry (AC-7, J5) ---------------------------------------------


def test_a_gemini_failure_marks_only_that_image_failed_and_retry_fixes_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-7
    use(monkeypatch, TaggingError("rate_limit"), good_result(title="Fine"))

    post(client, png_bytes("red"), png_bytes("blue"))

    failed, fine = one(client, 1), one(client, 2)
    assert (failed["status"], failed["error"]) == ("failed", "Rate limit reached")
    assert (fine["status"], fine["title"]) == ("tagged", "Fine")
    assert client.get("/api/images").status_code == 200  # the app keeps working

    retried = client.post("/api/images/1/retag")

    assert retried.status_code == 200
    again = one(client, 1)
    assert (again["status"], again["error"]) == ("tagged", None)


def test_a_busy_service_is_retried_but_other_errors_are_not(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    busy = TaggingError("other", transient=True)
    tagger = use(monkeypatch, busy, busy, good_result())

    post(client, png_bytes("red"))
    assert (tagger.calls, one(client, 1)["status"]) == (3, "tagged")  # two retries, then success

    unreadable = use(monkeypatch, TaggingError("bad_response", "MAX_TOKENS"))
    post(client, png_bytes("blue"))
    assert unreadable.calls == 1
    assert one(client, 2)["error"] == "Unreadable response from Gemini"


def test_a_busy_service_that_never_recovers_ends_as_failed_not_pending(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    tagger = use(monkeypatch, TaggingError("rate_limit", transient=True))

    post(client, png_bytes())

    assert tagger.calls == 3  # the first try and one per wait in RETRY_WAITS
    assert (one(client, 1)["status"], one(client, 1)["error"]) == ("failed", "Rate limit reached")


def test_an_unexpected_error_is_shown_as_tagging_error_and_logged_by_type_only(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    use(monkeypatch, ValueError(SECRET))

    with caplog.at_level(logging.WARNING, logger="app"):
        post(client, png_bytes())

    assert one(client, 1)["error"] == "Tagging error"
    assert "ValueError" in caplog.text and SECRET not in caplog.text


def test_a_missing_key_fails_the_image_without_leaking_anything(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No tagger fake: the real one runs and finds no key (conftest removed it).
    post(client, png_bytes())

    assert (one(client, 1)["status"], one(client, 1)["error"]) == ("failed", "Tagging error")


def test_retrying_a_tagged_image_is_refused_and_keeps_its_tags(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    tagger = use(monkeypatch, good_result(title="Keep me", tags=["keepme"]), TaggingError("rate_limit"))
    post(client, png_bytes())

    refused = client.post("/api/images/1/retag")

    assert refused.status_code == 409
    assert tagger.calls == 1  # Gemini was not asked again
    row = one(client, 1)
    assert (row["status"], row["title"], row["tags"]) == ("tagged", "Keep me", ["keepme"])
    assert titles(client, q="keepme") == ["Keep me"]


def test_retagging_an_image_that_is_already_pending_is_refused(client: TestClient) -> None:
    image_id, _ = db.add_pending("a" * 64, "x.webp")

    assert client.post(f"/api/images/{image_id}/retag").status_code == 409


def test_pending_images_left_by_a_previous_run_become_failed_on_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.init_db()
    image_id, _ = db.add_pending("a" * 64, "x.webp")

    with TestClient(main.app) as fresh:  # starting the app runs the startup rule
        row = fresh.get(f"/api/images/{image_id}").json()

    assert (row["status"], row["error"]) == ("failed", "Interrupted: the app was closed while tagging")


# --- search, flag, delete (AC-4, AC-8, AC-9, AC-10) ----------------------------


def test_a_word_that_is_only_in_the_text_finds_the_screenshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-4
    use(monkeypatch, good_result(title="Bakery", tags=["bread"], extracted_text="Order no. 48213"))
    post(client, png_bytes())

    assert titles(client, q="48213") == ["Bakery"]
    assert titles(client, q="4821") == ["Bakery"]  # prefix
    assert titles(client, q="99999") == []


def test_tags_outrank_text_in_the_results(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch,
        good_result(title="Text", tags=["x"], summary="x", extracted_text="we visited kyoto"),
        good_result(title="Tag", tags=["kyoto"], summary="x", extracted_text="x"))
    post(client, png_bytes("red"), png_bytes("blue"))

    assert titles(client, q="kyoto") == ["Tag", "Text"]


@pytest.mark.parametrize("q", ['"', "*", "AND", "OR", "NEAR(", "a OR", '" OR 1=1 --', "x*)", "'; DROP TABLE images;--",
                               "title:", "^a", "\u0000", "a" * 5000])
def test_odd_searches_give_results_or_an_empty_list_never_an_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, q: str
) -> None:  # AC-9
    use(monkeypatch)
    post(client, png_bytes())

    response = client.get("/api/images", params={"q": q})

    assert response.status_code == 200 and isinstance(response.json(), list)


def test_a_personal_info_image_is_hidden_until_asked_for(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-8, J6
    use(monkeypatch, good_result(title="Form", contains_personal_info=True), good_result(title="Fine"))
    post(client, png_bytes("red"), png_bytes("blue"))

    assert titles(client) == ["Fine"] and titles(client, q="form") == []
    assert titles(client, show_flagged="true") == ["Fine", "Form"]
    assert one(client, 1)["contains_personal_info"] is True  # still reachable directly


def test_delete_removes_the_file_the_rows_and_the_search_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-10
    use(monkeypatch)
    post(client, png_bytes())
    stored = list(db.images_dir().iterdir())
    assert len(stored) == 1 and titles(client, q="ramen") == ["Ramen shop near Shinjuku"]

    assert client.delete("/api/images/1").status_code == 204

    assert list(db.images_dir().iterdir()) == []
    assert titles(client, q="ramen") == [] and titles(client) == []
    assert client.get("/api/images/1").status_code == 404
    assert client.get("/api/images/1/file").status_code == 404
    assert client.delete("/api/images/1").status_code == 404


def test_an_image_deleted_while_it_is_being_tagged_gets_no_tags_and_no_search_entry(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def delete_then_answer():  # noqa: ANN202
        db.delete_image(1)
        return good_result(title="Ghost", tags=["ghost"])

    use(monkeypatch, delete_then_answer)

    post(client, png_bytes())

    assert titles(client) == [] and titles(client, q="ghost") == []
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM image_fts").fetchone()[0] == 0


def test_unknown_ids_are_a_404_and_a_non_number_is_rejected(client: TestClient) -> None:
    assert client.get("/api/images/42").status_code == 404
    assert client.get("/api/images/42/file").status_code == 404
    assert client.post("/api/images/42/retag").status_code == 404
    assert client.get("/api/images/abc").status_code == 422


def test_the_status_filter_only_accepts_known_values(client: TestClient) -> None:
    assert client.get("/api/images", params={"status": "bogus"}).status_code == 422
    assert client.get("/api/images", params={"limit": 0}).status_code == 422


def test_the_page_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AI Screenshot Repository" in response.text and 'id="grid"' in response.text


# --- robustness (from the fresh-context review) --------------------------------


@pytest.mark.parametrize("bad", ["99999999999999999999", "0", "-1"])
def test_ids_sqlite_cannot_hold_are_a_422_not_a_500(client: TestClient, bad: str) -> None:
    assert client.get(f"/api/images/{bad}").status_code == 422
    assert client.get(f"/api/images/{bad}/file").status_code == 422
    assert client.post(f"/api/images/{bad}/retag").status_code == 422
    assert client.delete(f"/api/images/{bad}").status_code == 422


def test_a_busy_service_is_not_retried_once_the_deadline_has_passed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:  # keeps AC-1's 60 s in reach
    minutes = iter(range(0, 10_000, 60))  # every reading of the clock is a minute later
    monkeypatch.setattr(main, "clock", lambda: next(minutes))
    tagger = use(monkeypatch, TaggingError("rate_limit", transient=True))

    post(client, png_bytes())

    assert tagger.calls == 1
    assert one(client, 1)["error"] == "Rate limit reached"


def test_a_database_error_while_recording_is_logged_by_type_and_does_not_escape(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    use(monkeypatch)

    def locked(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError(SECRET)

    monkeypatch.setattr(main.db, "set_tagged", locked)
    image_id, _ = db.add_pending("c" * 64, str(db.images_dir() / "x.webp"))
    (db.images_dir() / "x.webp").write_bytes(b"not read: the tagger is faked")

    with caplog.at_level(logging.WARNING, logger="app"):
        main.tag_task(image_id)  # called directly: in the real pool an escaping error would just vanish

    assert "OperationalError" in caplog.text and SECRET not in caplog.text


def test_a_failed_row_insert_leaves_no_orphan_file(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch)

    def broken(*args: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(main.db, "add_pending", broken)

    result = post(client, png_bytes()).json()

    assert result[0]["error"] == "could not be added"
    assert list(db.images_dir().iterdir()) == []


def test_delete_still_succeeds_when_the_file_cannot_be_removed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    use(monkeypatch)
    post(client, png_bytes())
    real_unlink = Path.unlink

    def locked(self: Path, *args: object, **kwargs: object) -> None:
        if self.suffix == ".webp":
            raise PermissionError(SECRET)  # Windows, while the file is being sent
        real_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", locked)

    assert client.delete("/api/images/1").status_code == 204
    assert client.get("/api/images/1").status_code == 404


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [("https://evil.example", False), ("http://evil.example:8000", False), ("null", False),
     ("http://127.0.0.1:8000", True), ("http://localhost:8000", True)],
)
def test_a_page_on_another_site_cannot_upload_or_delete(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, origin: str, allowed: bool
) -> None:
    tagger = use(monkeypatch)
    files = [("files", ("a.png", png_bytes(), "image/png"))]

    upload = client.post("/api/images", files=files, headers={"Origin": origin})

    assert (upload.status_code == 200) is allowed and tagger.calls == (1 if allowed else 0)
    expected = 204 if allowed else 403
    assert client.delete("/api/images/1", headers={"Origin": origin}).status_code == expected


def test_reading_is_not_blocked_by_the_origin_check(client: TestClient) -> None:
    assert client.get("/api/images", headers={"Origin": "https://evil.example"}).status_code == 200
