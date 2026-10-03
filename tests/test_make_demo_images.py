import random

import pytest
from PIL import ImageStat

from app.schemas import TagResult
from eval.make_demo_images import H, POSTS, W, post_screenshot


def test_post_names_are_unique_and_there_are_ten() -> None:
    assert len(POSTS) == len({p.name for p in POSTS}) == 10


@pytest.mark.parametrize("post", POSTS, ids=lambda p: p.name)
def test_the_tags_for_a_post_are_valid_tagger_output(post: object) -> None:
    TagResult(title=post.title, summary=post.summary, category=post.category, city=post.city,  # type: ignore[attr-defined]
              country=post.country, tags=post.tags, contains_personal_info=False, extracted_text="x")  # type: ignore[attr-defined]


def test_a_post_is_a_phone_sized_screenshot_and_is_the_same_every_time() -> None:
    post = POSTS[0]

    first = post_screenshot(post, random.Random(1))
    again = post_screenshot(post, random.Random(1))

    assert first.size == (W, H)
    assert first.tobytes() == again.tobytes()


def test_the_picture_area_has_real_detail_and_differs_between_posts() -> None:
    a = post_screenshot(POSTS[1], random.Random(2)).crop((0, 260, W, 1400))
    b = post_screenshot(POSTS[2], random.Random(3)).crop((0, 260, W, 1400))

    assert max(ImageStat.Stat(a.convert("L")).stddev) > 20  # not a flat colour
    assert ImageStat.Stat(a.convert("L")).mean != ImageStat.Stat(b.convert("L")).mean
