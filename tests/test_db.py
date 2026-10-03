import pytest

from app import db
from app.search import match_query
from helpers import good_result


@pytest.fixture(autouse=True)
def database() -> None:
    db.init_db()


def add(n: int = 1) -> int:
    return db.add_pending(f"{n:064d}", f"data/images/{n}.webp")[0]


def tagged(n: int = 1, **overrides: object) -> int:
    image_id = add(n)
    assert db.set_tagged(image_id, good_result(**overrides), "m", "v1")
    return image_id


def titles(query: str = "", **filters: object) -> list[object]:
    rows = db.list_images(match_query(query), filters.get("status"), bool(filters.get("show_flagged")), 40)  # type: ignore[arg-type]
    return [r["title"] for r in rows]


def test_a_new_image_is_pending_and_a_repeat_is_a_duplicate() -> None:
    first = db.add_pending("a" * 64, "x.webp")
    again = db.add_pending("a" * 64, "y.webp")

    assert first[1] is True and again == (first[0], False)
    assert db.find_by_sha("a" * 64) == {"id": first[0], "status": "pending"}
    assert db.find_by_sha("b" * 64) is None


def test_set_tagged_stores_the_fields_tags_and_a_search_entry() -> None:
    image_id = tagged(1, tags=["ramen", "shinjuku"])

    row = db.get_image(image_id)

    assert row is not None
    assert (row["status"], row["title"], row["city"], row["model"], row["prompt_version"]) == (
        "tagged", "Ramen shop near Shinjuku", "Tokyo", "m", "v1")
    assert row["tags"] == ["ramen", "shinjuku"] and row["extracted_text"] == "Open 11am to 9pm"
    assert titles("shinjuku") == ["Ramen shop near Shinjuku"]


def test_a_result_for_a_deleted_or_settled_image_is_discarded() -> None:
    gone = add(1)
    db.delete_image(gone)
    done = tagged(2)

    assert db.set_tagged(gone, good_result(), "m", "v1") is False
    assert db.set_tagged(done, good_result(title="Second"), "m", "v1") is False  # not pending any more
    assert db.get_image(gone) is None
    assert titles() == ["Ramen shop near Shinjuku"]  # nothing leaked into the index or the list


def test_a_deleted_images_id_is_never_given_to_a_new_image() -> None:
    first = add(1)
    db.delete_image(first)

    second = add(2)

    assert second != first
    # A late result for the deleted image must not land on the new one.
    assert db.set_tagged(first, good_result(title="Stale"), "m", "v1") is False
    row = db.get_image(second)
    assert row is not None and row["status"] == "pending" and row["title"] is None


def test_set_failed_records_the_message_once() -> None:
    image_id = add()

    assert db.set_failed(image_id, "Rate limit reached") is True
    assert db.set_failed(image_id, "Tagging error") is False
    row = db.get_image(image_id)
    assert row is not None and (row["status"], row["error"]) == ("failed", "Rate limit reached")


def test_a_failed_image_goes_back_to_pending_for_a_retry() -> None:
    image_id = add()
    db.set_failed(image_id, "Rate limit reached")

    assert db.reset_pending(image_id) is True

    row = db.get_image(image_id)
    assert row is not None and (row["status"], row["error"]) == ("pending", None)
    assert db.reset_pending(image_id) is False  # now pending, not failed
    assert db.reset_pending(999) is False


def test_a_tagged_image_cannot_be_reset_so_a_failed_retry_cannot_wipe_its_tags() -> None:
    image_id = tagged(1, title="Keep me", tags=["keepme"])

    assert db.reset_pending(image_id) is False

    row = db.get_image(image_id)
    assert row is not None and (row["status"], row["title"], row["tags"]) == ("tagged", "Keep me", ["keepme"])
    assert titles("keepme") == ["Keep me"]


def test_startup_marks_leftover_pending_images_as_interrupted() -> None:
    pending, done = add(1), tagged(2)

    assert db.mark_interrupted() == 1

    row = db.get_image(pending)
    assert row is not None and (row["status"], row["error"]) == ("failed", db.INTERRUPTED)
    other = db.get_image(done)
    assert other is not None and other["status"] == "tagged"


def test_delete_removes_the_row_tags_and_search_entry() -> None:
    image_id = tagged(1)

    assert db.delete_image(image_id) == "data/images/1.webp"

    assert db.get_image(image_id) is None
    assert titles("ramen") == [] and titles() == []
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM image_fts").fetchone()[0] == 0
    assert db.delete_image(image_id) is None


def test_the_list_is_newest_first_and_can_be_filtered_and_limited() -> None:
    for n in (1, 2, 3):
        tagged(n, title=f"Image {n}")
    add(4)

    assert titles() == [None, "Image 3", "Image 2", "Image 1"]
    assert titles(status="pending") == [None]
    assert titles(status="tagged") == ["Image 3", "Image 2", "Image 1"]
    assert len(db.list_images(None, None, False, 2)) == 2


def test_flagged_images_are_hidden_unless_asked_for() -> None:
    tagged(1, title="Fine")
    tagged(2, title="Private", contains_personal_info=True)

    assert titles() == ["Fine"]
    assert titles(show_flagged=True) == ["Private", "Fine"]
    assert titles("private") == []
    assert titles("private", show_flagged=True) == ["Private"]


def test_tags_summaries_and_places_rank_above_text() -> None:
    tagged(1, title="A", tags=["kyoto"], summary="x", extracted_text="x")
    tagged(2, title="B", tags=["x"], summary="x", extracted_text="we visited kyoto today")

    assert titles("kyoto") == ["A", "B"]


def test_prefix_and_multi_word_search() -> None:
    tagged(1, title="Ramen", city="Tokyo", tags=["noodles"])
    tagged(2, title="Sushi", city="Kyoto", tags=["fish"])

    assert titles("tok") == ["Ramen"]
    assert titles("tokyo noodles") == ["Ramen"]
    assert titles("tokyo fish") == []  # words are ANDed


def test_awkward_text_is_stored_and_searched_as_plain_data() -> None:
    tagged(1, title='He said "hi" -- OR 1=1; DROP TABLE images', tags=["it's", 'quote"d'])

    assert len(titles("drop")) == 1
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM images").fetchone()[0] == 1
