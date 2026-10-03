"""All SQL lives here. Every statement is a fixed string with bound parameters
(hard rule 4). Each call opens its own short-lived connection, so request threads
and background tagging threads never share one."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import TagResult

INTERRUPTED = "Interrupted: the app was closed while tagging"

SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    -- AUTOINCREMENT: ids are never reused. Otherwise a tagging task for a deleted
    -- image could finish after a new upload took its id, and tag the wrong image.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'tagged', 'failed')),
    error TEXT,
    title TEXT,
    summary TEXT,
    category TEXT,
    city TEXT,
    country TEXT,
    extracted_text TEXT,
    contains_personal_info INTEGER NOT NULL DEFAULT 0,
    model TEXT,
    prompt_version TEXT
);
CREATE TABLE IF NOT EXISTS tags (
    image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (image_id, tag)
);
CREATE VIRTUAL TABLE IF NOT EXISTS image_fts
    USING fts5(title, summary, tags, city, country, extracted_text);
"""

# Columns the library grid and detail view need. extracted_text is large, so only
# the detail query adds it. Tags come back as a JSON array from a subquery.
LIST_SELECT = """
SELECT i.id, i.created_at, i.status, i.error, i.title, i.summary, i.category, i.city,
       i.country, i.contains_personal_info, i.model, i.prompt_version,
       (SELECT json_group_array(t.tag) FROM tags t WHERE t.image_id = i.id) AS tags_json
"""
FILTERS = """
  AND (:status IS NULL OR i.status = :status)
  AND (:show_flagged = 1 OR i.contains_personal_info = 0)
"""
LIST_NEWEST = LIST_SELECT + """
FROM images i
WHERE 1 = 1""" + FILTERS + """
ORDER BY i.created_at DESC, i.id DESC
LIMIT :limit
"""
# Tags, city and country weigh more than the summary and the extracted text.
LIST_SEARCH = LIST_SELECT + """
FROM image_fts JOIN images i ON i.id = image_fts.rowid
WHERE image_fts MATCH :match""" + FILTERS + """
ORDER BY bm25(image_fts, 5.0, 2.0, 8.0, 6.0, 6.0, 1.0), i.id DESC
LIMIT :limit
"""
GET_ONE = LIST_SELECT.rstrip() + ", i.extracted_text, i.file_path FROM images i WHERE i.id = ?"


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "data"))


def images_dir() -> Path:
    return data_dir() / "images"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(data_dir() / "app.db", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:  # commits on success, rolls back on an exception
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    images_dir().mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)


def _row(row: sqlite3.Row) -> dict[str, object]:
    out = dict(row)
    out["tags"] = sorted(json.loads(out.pop("tags_json") or "[]"))
    out["contains_personal_info"] = bool(out["contains_personal_info"])
    return out


def find_by_sha(sha256: str) -> dict[str, object] | None:
    with connect() as conn:
        found = conn.execute("SELECT id, status FROM images WHERE sha256 = ?", (sha256,)).fetchone()
    return dict(found) if found else None


def add_pending(sha256: str, file_path: str) -> tuple[int, bool]:
    """Returns (id, created). created is False if this file is already in the library."""
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO images (sha256, file_path, created_at, status) VALUES (?, ?, ?, 'pending') "
            "ON CONFLICT(sha256) DO NOTHING",
            (sha256, file_path, now),
        )
        created = cursor.rowcount == 1
        image_id = conn.execute("SELECT id FROM images WHERE sha256 = ?", (sha256,)).fetchone()["id"]
    return image_id, created


def set_tagged(image_id: int, result: TagResult, model: str, prompt_version: str) -> bool:
    """Store a result. False means the image was deleted or is no longer pending
    while Gemini worked, so the result is discarded: no tags, no search entry."""
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE images SET status = 'tagged', error = NULL, title = ?, summary = ?, category = ?, "
            "city = ?, country = ?, extracted_text = ?, contains_personal_info = ?, model = ?, "
            "prompt_version = ? WHERE id = ? AND status = 'pending'",
            (result.title, result.summary, result.category, result.city, result.country,
             result.extracted_text, int(result.contains_personal_info), model, prompt_version, image_id),
        )
        if cursor.rowcount == 0:
            return False
        conn.execute("DELETE FROM tags WHERE image_id = ?", (image_id,))
        conn.executemany("INSERT INTO tags (image_id, tag) VALUES (?, ?)",
                         [(image_id, tag) for tag in result.tags])
        conn.execute("DELETE FROM image_fts WHERE rowid = ?", (image_id,))
        conn.execute(
            "INSERT INTO image_fts (rowid, title, summary, tags, city, country, extracted_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (image_id, result.title, result.summary, " ".join(result.tags), result.city,
             result.country, result.extracted_text),
        )
    return True


def set_failed(image_id: int, message: str) -> bool:
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE images SET status = 'failed', error = ? WHERE id = ? AND status = 'pending'",
            (message, image_id),
        )
    return cursor.rowcount == 1


def reset_pending(image_id: int) -> bool:
    """Retag: back to pending with the AI fields cleared, so a pending image has no
    tags and no search entry. False if it is missing or already pending."""
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE images SET status = 'pending', error = NULL, title = NULL, summary = NULL, "
            "category = NULL, city = NULL, country = NULL, extracted_text = NULL, "
            "contains_personal_info = 0, model = NULL, prompt_version = NULL "
            "WHERE id = ? AND status IN ('tagged', 'failed')",
            (image_id,),
        )
        if cursor.rowcount == 0:
            return False
        conn.execute("DELETE FROM tags WHERE image_id = ?", (image_id,))
        conn.execute("DELETE FROM image_fts WHERE rowid = ?", (image_id,))
    return True


def mark_interrupted() -> int:
    """On startup: anything still pending was cut off by a restart."""
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE images SET status = 'failed', error = ? WHERE status = 'pending'", (INTERRUPTED,)
        )
    return cursor.rowcount


def list_images(match: str | None, status: str | None, show_flagged: bool, limit: int) -> list[dict[str, object]]:
    params = {"match": match, "status": status, "show_flagged": int(show_flagged), "limit": limit}
    with connect() as conn:  # sqlite3 ignores named parameters a statement doesn't use
        rows = conn.execute(LIST_SEARCH if match else LIST_NEWEST, params).fetchall()
    return [_row(r) for r in rows]


def get_image(image_id: int) -> dict[str, object] | None:
    with connect() as conn:
        row = conn.execute(GET_ONE, (image_id,)).fetchone()
    return _row(row) if row else None


def delete_image(image_id: int) -> str | None:
    """Remove the row, its tags and its search entry. Returns the file path for the
    caller to delete, or None if there was no such image."""
    with connect() as conn:
        row = conn.execute("SELECT file_path FROM images WHERE id = ?", (image_id,)).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM image_fts WHERE rowid = ?", (image_id,))
        conn.execute("DELETE FROM images WHERE id = ?", (image_id,))  # tags cascade
    return str(row["file_path"])
