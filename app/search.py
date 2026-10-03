"""Turns what a person types into a safe FTS5 query."""

import re

MAX_TERMS = 10


def match_query(text: str) -> str | None:
    """`tok ramen` becomes `"tok"* "ramen"*`: every word is a quoted prefix match and
    they are ANDed. Only letters and digits survive, so quotes, `*`, `AND`, `NEAR(`
    and the rest of FTS5's syntax can't change the query (hard rule 4, AC-9).
    Returns None when nothing searchable is left, which means "no search"."""
    terms = re.findall(r"[^\W_]+", text.casefold())[:MAX_TERMS]
    return " ".join(f'"{term}"*' for term in terms) or None
