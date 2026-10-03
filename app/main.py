"""Routes and startup."""

import logging
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response, UploadFile
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse

from app import db, images
from app.schemas import TagResult
from app.search import match_query
from app.tagger import MESSAGES, PROMPT_VERSION, TaggingError, model_name, tag_image

load_dotenv()  # reads .env into the environment; the tests clear the key before each test

# Resolved from this file, not the working directory, so the app runs from anywhere.
STATIC_DIR = Path(__file__).parent / "static"

MAX_FILES = 20
MAX_TAGGING_AT_ONCE = 3
RETRY_WAITS = (5, 15)  # seconds before each retry when the service says "try later"
TAGGING_DEADLINE_S = 50  # no retry once this much time is gone (AC-1 wants 60 s)
clock = time.monotonic  # a name of its own, so a test can fake the passing of time
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
ImageId = Annotated[int, PathParam(ge=1, le=2**63 - 1)]  # larger ids overflow SQLite

logger = logging.getLogger("app")

# Tagging runs on its own small pool, so waiting tasks can't use up the threads that
# serve requests. Created at startup; the tests swap in one that runs inline.
tagging_pool: ThreadPoolExecutor | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global tagging_pool
    db.init_db()
    db.mark_interrupted()
    tagging_pool = ThreadPoolExecutor(max_workers=MAX_TAGGING_AT_ONCE, thread_name_prefix="tagging")
    yield
    tagging_pool.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="AI Screenshot Repository", lifespan=lifespan)


@app.middleware("http")
async def refuse_foreign_origins(request: Request, call_next):  # noqa: ANN001, ANN201
    """A page on another site could make the browser POST to this local server and
    spend the Gemini quota. Browsers name the page in `Origin`, so refuse any
    changing request that comes from somewhere other than this machine."""
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
        if urlparse(origin).hostname not in LOCAL_HOSTS:
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
    return await call_next(request)


# --- tagging in the background -------------------------------------------------


def tag_with_retries(data: bytes) -> TagResult:
    """Retries a busy service (429 or 5xx) after each wait in RETRY_WAITS, unless
    the deadline for this image has passed."""
    started = clock()
    for wait in (*RETRY_WAITS, None):
        try:
            return tag_image(data, "image/webp")
        except TaggingError as exc:
            out_of_time = wait is not None and clock() - started + wait >= TAGGING_DEADLINE_S
            if wait is None or not exc.transient or out_of_time:
                raise
            time.sleep(wait)
    raise AssertionError("unreachable")


def tag_outcome(path: Path) -> tuple[TagResult, str] | str:
    """The result and the model that made it, or the fixed failure message. Failures
    are logged by type only: the details could carry text from the screenshot (rule 2)."""
    try:
        result = tag_with_retries(path.read_bytes())
        return result, model_name()
    except TaggingError as exc:
        logger.warning("tagging failed: %s (%s)", exc.kind, exc.finish_reason)
        return exc.message
    except Exception as exc:  # also a missing key or model, which are not per-image problems
        logger.warning("tagging failed: %s", type(exc).__name__)
        return MESSAGES["other"]


def tag_task(image_id: int) -> None:
    """Tag one stored image and record the outcome. Never raises: an exception in a
    pool thread would only be lost."""
    try:
        row = db.get_image(image_id)
        if row is None or row["status"] != "pending":
            return
        outcome = tag_outcome(Path(str(row["file_path"])))
        if isinstance(outcome, str):
            db.set_failed(image_id, outcome)
        else:
            db.set_tagged(image_id, outcome[0], outcome[1], PROMPT_VERSION)  # False: deleted meanwhile
    except Exception as exc:  # for example a locked or full database
        logger.warning("could not record the tagging outcome: %s", type(exc).__name__)


def queue_tagging(image_id: int) -> None:
    assert tagging_pool is not None, "the app has not started"
    tagging_pool.submit(tag_task, image_id)


# --- helpers -------------------------------------------------------------------

PUBLIC_FIELDS = ("id", "created_at", "status", "error", "title", "summary", "category",
                 "city", "country", "contains_personal_info", "model", "prompt_version", "tags")


def public(row: dict[str, object], detail: bool = False) -> dict[str, object]:
    """Only the fields the browser needs: never the hash or the stored file path."""
    fields = PUBLIC_FIELDS + (("extracted_text",) if detail else ())
    return {name: row[name] for name in fields}


def add_one(data: bytes) -> dict[str, object]:
    """Check, de-duplicate, store and queue one upload. Never raises."""
    try:
        images.check_upload(data)
        digest = images.sha256(data)
        existing = db.find_by_sha(digest)  # before compressing, saving or calling Gemini
        if existing is not None:
            return {"id": existing["id"], "status": existing["status"], "duplicate": True, "error": None}
        path = images.store(data, digest, db.images_dir())
        try:
            image_id, created = db.add_pending(digest, str(path))
        except Exception:
            path.unlink(missing_ok=True)  # no row will ever point at this file
            raise
        if created:
            queue_tagging(image_id)
        return {"id": image_id, "status": "pending" if created else None, "duplicate": not created, "error": None}
    except images.RejectedImage as exc:
        return {"id": None, "status": None, "duplicate": False, "error": str(exc)}
    except Exception as exc:
        logger.warning("adding an upload failed: %s", type(exc).__name__)
        return {"id": None, "status": None, "duplicate": False, "error": "could not be added"}


# --- routes --------------------------------------------------------------------


@app.get("/")
def library_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/images")
def upload(files: list[UploadFile]) -> list[dict[str, object]]:
    """One result per file, in the order sent. The uploaded names are never used."""
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"You can add up to {MAX_FILES} screenshots at a time.")
    return [add_one(f.file.read(images.MAX_BYTES + 1)) for f in files]


@app.get("/api/images")
def list_images(
    q: str = "",
    status: Literal["pending", "tagged", "failed"] | None = None,
    show_flagged: bool = False,
    limit: int = Query(40, ge=1, le=100),
) -> list[dict[str, object]]:
    rows = db.list_images(match_query(q), status, show_flagged, limit)
    return [public(r) for r in rows]


@app.get("/api/images/{image_id}")
def get_image(image_id: ImageId) -> dict[str, object]:
    row = db.get_image(image_id)
    if row is None:
        raise HTTPException(404, "Not found")
    return public(row, detail=True)


@app.get("/api/images/{image_id}/file")
def get_image_file(image_id: ImageId) -> FileResponse:
    row = db.get_image(image_id)
    path = Path(str(row["file_path"])) if row else None
    if path is None or not path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="image/webp")


@app.post("/api/images/{image_id}/retag")
def retag(image_id: ImageId) -> dict[str, object]:
    if db.get_image(image_id) is None:
        raise HTTPException(404, "Not found")
    if not db.reset_pending(image_id):
        raise HTTPException(409, "Already being tagged")
    queue_tagging(image_id)
    row = db.get_image(image_id)
    if row is None:  # deleted in the instant since the reset
        raise HTTPException(404, "Not found")
    return public(row, detail=True)


@app.delete("/api/images/{image_id}", status_code=204)
def delete_image(image_id: ImageId) -> Response:
    file_path = db.delete_image(image_id)
    if file_path is None:
        raise HTTPException(404, "Not found")
    path = Path(file_path)
    if db.find_by_sha(path.stem) is None:  # a re-upload may have claimed the file meanwhile
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:  # on Windows, a file still being sent can't be removed yet
            logger.warning("could not remove a stored file: %s", type(exc).__name__)
    return Response(status_code=204)
