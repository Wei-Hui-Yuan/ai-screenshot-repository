import re

import pytest

from app.search import MAX_TERMS, match_query


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("tokyo", '"tokyo"*'),
        ("  Tokyo   RAMEN ", '"tokyo"* "ramen"*'),
        ("São", '"são"*'),
        ("1,280", '"1"* "280"*'),
        ("tokyo-ramen_shop", '"tokyo"* "ramen"* "shop"*'),
        # FTS5 syntax typed by accident or on purpose is just words
        ("AND", '"and"*'),
        ("a OR b", '"a"* "or"* "b"*'),
        ("NEAR(a b)", '"near"* "a"* "b"*'),
        ("title:tokyo", '"title"* "tokyo"*'),
    ],
)
def test_words_become_quoted_prefix_terms(typed: str, expected: str) -> None:
    assert match_query(typed) == expected


@pytest.mark.parametrize("typed", ["", "   ", '"', "*", '"*"', "()", "^", "-", "+ - ~", "\x00"])
def test_nothing_searchable_means_no_search(typed: str) -> None:
    assert match_query(typed) is None


def test_only_a_few_words_are_used() -> None:
    assert match_query(" ".join(f"w{i}" for i in range(50))).count('"*') == MAX_TERMS  # type: ignore[union-attr]


@pytest.mark.parametrize("typed", ['" OR 1=1 --', 'a" OR "b', "x*) AND (y", "'; DROP TABLE images; --", "\"\"\"\""])
def test_whatever_is_typed_only_letters_and_digits_reach_the_query(typed: str) -> None:
    out = match_query(typed)

    assert out is None or re.fullmatch(r'"\w+"\*( "\w+"\*)*', out)
