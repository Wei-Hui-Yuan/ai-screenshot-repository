"""Tagging eval harness. Runs screenshots through tag_image at several image sizes
and models, scores the results against hand-written labels, and saves the raw
results. This is the only code that calls the real Gemini API (hard rule 8).

    python -m eval.run_eval --dry-run                              # no API calls
    python -m eval.run_eval --only ramen.png --sizes original      # smoke test
    python -m eval.run_eval --repeats 2                            # the full grid

Labels (eval/labels.json) are keyed by file name. City and country may be null,
and a place must match the label exactly (ignoring case). `queries` are searches
that should find the screenshot. `text_queries` are distinctive words that appear
only in its text, not expected as tags (AC-4). Both are optional:

    {"ramen.png": {"city": "Tokyo", "country": "Japan", "category": "food",
                   "contains_personal_info": false, "queries": ["tokyo", "ramen"],
                   "text_queries": ["1,280"]}}

Query matching approximates the planned FTS5 search: each word is a prefix match
on a word in title, summary, tags, place or extracted text. It ignores case,
accents and punctuation, but not FTS5's phrase rule for words like "1,280".

Output goes to eval/results/ (git-ignored: it holds text extracted from the
screenshots). The terminal shows titles and places, never extracted text.
"""

import argparse
import io
import json
import re
import sys
import time
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel, ConfigDict, ValidationError

from app import tagger
from app.images import compress
from app.schemas import Category, TagResult
from app.tagger import TaggingError, Usage, tag_image_with_usage

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MIME_BY_FORMAT = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
ORIGINAL = "original"
MAX_CONSECUTIVE_UNAVAILABLE = 3  # then stop and keep what we have
PLACE_QUERY_TARGET = 0.8  # G3
VALID_JSON_TARGET = 0.9  # G5

TagFn = Callable[[bytes, str, str | None], tuple[TagResult, Usage]]


class LabelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a typo in the labels file should fail loudly

    city: str | None
    country: str | None
    category: Category
    contains_personal_info: bool | None = None
    queries: list[str] = []
    text_queries: list[str] = []


@dataclass(frozen=True)
class Score:
    place_ok: bool | None  # None: the image has no stated place
    false_place: bool | None  # None: the image has a stated place
    category_ok: bool
    flag_ok: bool | None  # None: the label doesn't say
    place_queries: dict[str, str]  # query -> "miss" | "text-only" | "indexed"
    other_queries: dict[str, str]
    text_queries: dict[str, str]


@dataclass
class Row:
    image: str
    size: str
    model: str
    repeat: int
    labelled: bool = False
    attempts: int = 1  # more than 1: the service was busy and we retried
    bytes_sent: int | None = None
    seconds: float | None = None
    usage: Usage | None = None
    result: dict[str, object] | None = None
    error: dict[str, object] | None = None
    score: Score | None = None


@dataclass(frozen=True)
class Config:
    images: Path
    labels: Path
    sizes: list[str]
    models: list[str]
    repeats: int
    delay: float
    only: list[str]
    out: Path
    dry_run: bool
    retries: int = 0  # extra attempts after a 429 or 5xx, each a real call
    retry_wait: float = 0.0


# --- scoring: pure functions ---------------------------------------------------


def words(text: str) -> list[str]:
    """Lowercase words without accents or punctuation, as FTS5's tokenizer sees them."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.findall(r"[^\W_]+", plain)


def query_fields(query: str, result: TagResult) -> set[str] | None:
    """Which fields a search for `query` would match, or None for a miss.

    Every word is a prefix match, and different words can match in different
    fields."""
    terms = words(query)
    if not terms:
        return None
    fields = {
        "title": words(result.title),
        "summary": words(result.summary),
        "tags": words(" ".join(result.tags)),
        "place": words(f"{result.city or ''} {result.country or ''}"),
        "text": words(result.extracted_text),
    }
    matched: set[str] = set()
    for term in terms:
        hit = {name for name, found in fields.items() if any(w.startswith(term) for w in found)}
        if not hit:
            return None
        matched |= hit
    return matched


def classify_query(query: str, result: TagResult) -> str:
    fields = query_fields(query, result)
    if fields is None:
        return "miss"
    return "text-only" if fields == {"text"} else "indexed"


def same_place(expected: str | None, found: str | None) -> bool:
    if expected is None or found is None:
        return expected is None and found is None
    return expected.strip().casefold() == found.strip().casefold()


def is_place_query(query: str, label: LabelEntry) -> bool:
    return words(query) in [words(p) for p in (label.city, label.country) if p]


def score(label: LabelEntry, result: TagResult) -> Score:
    place_ok = false_place = None
    if label.city is not None or label.country is not None:
        place_ok = same_place(label.city, result.city) and same_place(label.country, result.country)
    else:
        false_place = result.city is not None or result.country is not None
    flag = label.contains_personal_info
    return Score(
        place_ok=place_ok,
        false_place=false_place,
        category_ok=result.category == label.category,
        flag_ok=None if flag is None else result.contains_personal_info == flag,
        place_queries={q: classify_query(q, result) for q in label.queries if is_place_query(q, label)},
        other_queries={q: classify_query(q, result) for q in label.queries if not is_place_query(q, label)},
        text_queries={q: classify_query(q, result) for q in label.text_queries},
    )


def ratio(hits: int, total: int) -> str:
    return f"{hits}/{total}" if total else "n/a"


def gate(passed: bool | None) -> str:
    return "n/a" if passed is None else ("PASS" if passed else "FAIL")


def judge(passed: bool | None, labelled: bool, complete: bool) -> str:
    """A gate verdict. It is INCOMPLETE if any labelled call has no score (it failed
    or was rate-limited), because a pass on the rest would prove nothing."""
    if not labelled:
        return "n/a"
    return "INCOMPLETE" if not complete else gate(passed)


def is_transient(error: dict[str, object] | None) -> bool:
    """A 429 or a 5xx (such as 503 UNAVAILABLE): the service said try later. It says
    nothing about tagging quality, so it is never a loss, a failure or instability."""
    if not error:
        return False
    code = error.get("api_code")
    return error.get("kind") == "rate_limit" or (isinstance(code, int) and code >= 500)


def signature(row: Row) -> object:
    if row.error:
        return ("error", row.error.get("type"), row.error.get("kind"))
    s = row.score
    if s is None:
        return None
    return (s.place_ok, s.false_place, s.category_ok, s.flag_ok, tuple(sorted(s.place_queries.items())),
            tuple(sorted(s.other_queries.items())), tuple(sorted(s.text_queries.items())))


def mean(values: list[float] | list[int]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def hits(queries: list[str]) -> int:
    return sum(v != "miss" for v in queries)


def summarise_group(model: str, size: str, rows: list[Row]) -> dict[str, object]:
    labelled = [r for r in rows if r.labelled]
    scored = [r.score for r in rows if r.score is not None]
    complete = all(r.score is not None for r in labelled)
    valid = sum(r.result is not None for r in rows)
    attempted = sum(not is_transient(r.error) for r in rows)
    place = [s.place_ok for s in scored if s.place_ok is not None]
    false = [s.false_place for s in scored if s.false_place is not None]
    flags = [s.flag_ok for s in scored if s.flag_ok is not None]
    place_q = [v for s in scored for v in s.place_queries.values()]
    other_q = [v for s in scored for v in s.other_queries.values()]
    text_q = [v for s in scored for v in s.text_queries.values()]
    cells: dict[str, list[Row]] = {}
    for row in rows:
        if not is_transient(row.error):  # a 429 or 503 says nothing about stability
            cells.setdefault(row.image, []).append(row)
    repeated = [group for group in cells.values() if len(group) > 1]
    usages = [r.usage for r in rows if r.usage]
    return {
        "model": model,
        "size": size,
        "calls": len(rows),
        "valid": valid,
        "unavailable": len(rows) - attempted,
        "retries": sum(r.attempts - 1 for r in rows),
        "scored": ratio(len(scored), len(labelled)),
        "place_ok": ratio(sum(place), len(place)),
        "false_place": ratio(sum(false), len(false)),
        "category_ok": ratio(sum(s.category_ok for s in scored), len(scored)),
        "flag_ok": ratio(sum(flags), len(flags)),
        "place_queries": ratio(hits(place_q), len(place_q)),
        "other_queries": ratio(hits(other_q), len(other_q)),
        "text_queries": ratio(hits(text_q), len(text_q)),
        "mean_seconds": mean([r.seconds for r in rows if r.seconds is not None]),
        "mean_prompt_tokens": mean([u.prompt_tokens for u in usages if u.prompt_tokens]),
        "mean_thought_tokens": mean([u.thought_tokens for u in usages if u.thought_tokens]),
        "unstable_cells": sum(len({signature(r) for r in g}) > 1 for g in repeated) if repeated else None,
        "G1_no_false_place": judge(None if not false else not any(false), bool(labelled), complete),
        "G2_places_right": judge(None if not place else all(place), bool(labelled), complete),
        "G3_place_queries": judge(
            None if not place_q else hits(place_q) / len(place_q) >= PLACE_QUERY_TARGET, bool(labelled), complete
        ),
        "G4_text_queries": judge(None if not text_q else hits(text_q) == len(text_q), bool(labelled), complete),
        "G5_valid_json": gate(None if attempted == 0 else valid / attempted >= VALID_JSON_TARGET),
    }


def summarise(rows: list[Row]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[Row]] = {}
    for row in rows:
        groups.setdefault((row.model, row.size), []).append(row)
    return [summarise_group(model, size, group) for (model, size), group in groups.items()]


def failed_checks(row: Row) -> list[str]:
    if row.error:
        return [f"ERR:{row.error.get('kind') or row.error.get('type')}"]
    s = row.score
    if s is None:
        return []
    checks = [("place", s.place_ok is False), ("false-place", bool(s.false_place)),
              ("category", not s.category_ok), ("flag", s.flag_ok is False)]
    queries = s.place_queries | s.other_queries | s.text_queries
    return [name for name, bad in checks if bad] + [f"q:{q}" for q, v in queries.items() if v == "miss"]


def cell_verdict(group: list[Row]) -> str:
    """One image at one size: 'ok' if every check passed, else what failed."""
    if not group:
        return "-"
    if any(is_transient(r.error) for r in group):
        return "INCOMPLETE"
    if all(not r.labelled and not r.error for r in group):
        return "unscored"
    outcomes = [frozenset(failed_checks(r)) for r in group]
    failed = ",".join(sorted(set().union(*outcomes)))
    if len(set(outcomes)) > 1:
        return f"unstable[{failed}]"
    return failed or "ok"


def format_grid(rows: list[Row]) -> list[str]:
    """An image x size table per model, and where a smaller size lost something
    the original passed (the plan's size rule)."""
    lines: list[str] = []
    for model in dict.fromkeys(r.model for r in rows):
        mine = [r for r in rows if r.model == model]
        sizes = list(dict.fromkeys(r.size for r in mine))
        images = list(dict.fromkeys(r.image for r in mine))
        cell = {(i, s): cell_verdict([r for r in mine if r.image == i and r.size == s])
                for i in images for s in sizes}
        name_w = max(len(i) for i in images)
        widths = [max(len(s), *(len(cell[(i, s)]) for i in images)) for s in sizes]
        lines.append(f"Grid for {model} (ok = every check passed):")
        lines.append("  " + " " * name_w + "  " + "  ".join(s.ljust(w) for s, w in zip(sizes, widths)))
        for i in images:
            lines.append("  " + i.ljust(name_w) + "  "
                         + "  ".join(cell[(i, s)].ljust(w) for s, w in zip(sizes, widths)))
        if ORIGINAL in sizes:
            lost = [f"{i}@{s} [{cell[(i, s)]}]" for i in images for s in sizes
                    if s != ORIGINAL and cell[(i, ORIGINAL)] == "ok" and cell[(i, s)] not in ("ok", "INCOMPLETE", "-")]
            lines.append("  Lost vs original: " + ("; ".join(lost) if lost else "nothing"))
    return lines


# --- running -------------------------------------------------------------------


def load_labels(path: Path) -> dict[str, LabelEntry]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))  # utf-8-sig: some editors add a BOM
    labels: dict[str, LabelEntry] = {}
    for name, entry in raw.items():
        try:
            labels[name] = LabelEntry.model_validate(entry)
        except ValidationError as exc:
            raise ValueError(f"Bad label for {name}: {exc}") from exc
    return labels


def list_images(folder: Path, only: list[str]) -> list[Path]:
    paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    return [p for p in paths if not only or p.name in only]


def prepare(path: Path, size: str) -> tuple[bytes, str]:
    data = path.read_bytes()
    if size != ORIGINAL:
        return compress(data, max_edge=int(size)), "image/webp"
    with Image.open(io.BytesIO(data)) as image:  # decode, don't trust the extension (rule 6)
        mime = MIME_BY_FORMAT.get(image.format or "")
    if mime is None:
        raise ValueError("not a PNG, JPEG or WebP image")
    return data, mime


def describe_error(exc: Exception) -> dict[str, object]:
    """Only types and codes: never str(exc), which could carry screenshot text."""
    info: dict[str, object] = {"type": type(exc).__name__}
    if isinstance(exc, TaggingError):
        info |= {"kind": exc.kind, "finish_reason": exc.finish_reason}
    cause = exc.__cause__
    if cause is not None:
        info |= {
            "cause_type": type(cause).__name__,
            "api_code": getattr(cause, "code", None),
            "api_status": getattr(cause, "status", None),
        }
        if info["api_code"] == 429:
            info |= quota_info(getattr(cause, "details", None))
    return info


def quota_info(details: object) -> dict[str, object]:
    """Which quota a 429 hit, from Google's structured error fields only (the
    quota id says per-day or per-minute). The free-text message is never read."""
    items = details.get("error", {}).get("details", []) if isinstance(details, dict) else []
    found: dict[str, object] = {}
    for item in items if isinstance(items, list) else []:
        kind = str(item.get("@type", "")) if isinstance(item, dict) else ""
        if kind.endswith("QuotaFailure") and item.get("violations"):
            violation = item["violations"][0]
            dimensions = violation.get("quotaDimensions") or {}
            found |= {"quota_id": violation.get("quotaId"), "quota_value": violation.get("quotaValue"),
                      "quota_model": dimensions.get("model")}
        elif kind.endswith("RetryInfo"):
            found["retry_delay"] = item.get("retryDelay")
    return {k: v for k, v in found.items() if isinstance(v, (str, int))}


def call_one(
    row: Row, path: Path, label: LabelEntry | None, tag: TagFn,
    retries: int = 0, wait: float = 0.0, sleep: Callable[[float], None] = time.sleep,
) -> TagResult | None:
    """Fill in `row`. Returns the result, or None if this call failed. A 429 or
    5xx is retried up to `retries` times. `row.attempts` records how many it took,
    and `row.seconds` is the last attempt's."""
    row.labelled = label is not None
    try:
        data, mime = prepare(path, row.size)
    except Exception as exc:  # an unreadable image must not end the run
        row.error, row.seconds = describe_error(exc), 0.0
        return None
    row.bytes_sent = len(data)
    for attempt in range(1, retries + 2):
        row.attempts = attempt
        started = time.perf_counter()
        try:
            result, row.usage = tag(data, mime, row.model)
        except RuntimeError:
            raise  # not configured: stop the whole run. The message has no secrets.
        except Exception as exc:  # one bad call must not end the run
            row.seconds = round(time.perf_counter() - started, 2)
            row.error = describe_error(exc)
            if isinstance(exc, TaggingError):
                row.usage = exc.usage  # token counts for a cut-off or unreadable reply
            if is_transient(row.error) and attempt <= retries:
                sleep(wait)
                continue
            return None
        row.seconds = round(time.perf_counter() - started, 2)
        row.error = None  # an earlier attempt may have failed
        row.result = result.model_dump()
        if label is not None:
            row.score = score(label, result)
        return result
    return None  # unreachable: the last attempt always returns


def progress_line(n: int, total: int, row: Row, result: TagResult | None) -> str:
    tries = f" (try {row.attempts})" if row.attempts > 1 else ""
    head = f"[{n:>2}/{total}] {row.image[:28]:<28} {row.size:>8} {row.seconds or 0:>6.1f}s{tries}  "
    if result is None:
        error = row.error or {}
        keys = ("kind", "finish_reason", "api_code", "api_status", "quota_id", "quota_value", "retry_delay")
        detail = " ".join(f"{k}={error[k]}" for k in keys if error.get(k))
        return f"{head}FAILED {error.get('type')} {detail}".rstrip()
    place = ", ".join(p for p in (result.city, result.country) if p) or "-"
    flag = "yes" if result.contains_personal_info else "no"
    return (f"{head}{result.category:<8} {result.title[:34]:<34} place={place} "
            f"tags={len(result.tags)} text={len(result.extracted_text)}ch flag={flag}")


def run(cfg: Config, tag: TagFn = tag_image_with_usage,
        sleep: Callable[[float], None] = time.sleep) -> list[Row]:
    images = list_images(cfg.images, cfg.only)
    labels = load_labels(cfg.labels) if cfg.labels.exists() else {}
    if not labels:
        print("No labels file: results are saved but not scored.")
    unlabelled = [p.name for p in images if p.name not in labels]
    if labels and unlabelled:
        print(f"Note: no label for {', '.join(unlabelled)}. They run but are not scored.")
    if not cfg.only:
        for name in sorted(set(labels) - {p.name for p in images}):
            print(f"Note: {name} is in the labels but there is no such image.")
    plan = [(m, p, s, r) for m in cfg.models for p in images for s in cfg.sizes for r in range(cfg.repeats)]
    print(f"{len(images)} images x {len(cfg.sizes)} sizes x {len(cfg.models)} models x "
          f"{cfg.repeats} repeats = {len(plan)} calls. Prompt {tagger.PROMPT_VERSION} ({tagger.PROMPT_HASH}).")
    if cfg.dry_run:
        for path in images:
            for size in cfg.sizes:
                data, mime = prepare(path, size)
                print(f"  {path.name:<28} {size:>8}  {len(data):>9,} bytes  {mime}")
        return []

    rows: list[Row] = []
    streak = 0
    try:
        for n, (model, path, size, repeat) in enumerate(plan, start=1):
            row = Row(image=path.name, size=size, model=model, repeat=repeat)
            result = call_one(row, path, labels.get(path.name), tag, cfg.retries, cfg.retry_wait, sleep)
            rows.append(row)
            print(progress_line(n, len(plan), row, result), flush=True)
            streak = streak + 1 if is_transient(row.error) else 0
            if streak >= MAX_CONSECUTIVE_UNAVAILABLE:
                print(f"Stopping: the service was unavailable {streak} times in a row. "
                      "Re-run the rest later with --only.")
                break
            if n < len(plan):
                sleep(cfg.delay)
    finally:
        if rows:  # also on Ctrl-C or a configuration error, so no paid call is lost
            print_summary(rows)
            print(f"Saved {save(cfg, rows)}")
    return rows


def print_summary(rows: list[Row]) -> None:
    print("\nPer model and size. G1 no invented place, G2 places right, G3 place queries >= 80%,")
    print("G4 text-only queries found, G5 valid JSON >= 90%. INCOMPLETE: some labelled calls have no score.")
    for s in summarise(rows):
        print(f"  {s['model']} @ {s['size']}: calls={s['calls']} valid={s['valid']} "
              f"unavailable={s['unavailable']} retries={s['retries']} scored={s['scored']} | place={s['place_ok']} "
              f"false_place={s['false_place']} category={s['category_ok']} flag={s['flag_ok']}")
        unstable = "n/a (needs --repeats 2)" if s["unstable_cells"] is None else s["unstable_cells"]
        print(f"      place_q={s['place_queries']} other_q={s['other_queries']} text_q={s['text_queries']} | "
              f"{s['mean_seconds']}s, prompt_tok={s['mean_prompt_tokens']}, "
              f"thought_tok={s['mean_thought_tokens']} | unstable cells={unstable}")
        print(f"      G1={s['G1_no_false_place']} G2={s['G2_places_right']} G3={s['G3_place_queries']} "
              f"G4={s['G4_text_queries']} G5={s['G5_valid_json']}")
    print()
    for line in format_grid(rows):
        print(line)


def save(cfg: Config, rows: list[Row]) -> Path:
    cfg.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", "+".join(cfg.models))
    path = cfg.out / f"{stamp}-{name}.json"
    document = {
        "saved": datetime.now().isoformat(timespec="seconds"),
        "prompt_version": tagger.PROMPT_VERSION,
        "prompt_hash": tagger.PROMPT_HASH,
        "config": {k: str(v) if isinstance(v, Path) else v for k, v in asdict(cfg).items()},
        "summary": summarise(rows),
        "rows": [asdict(r) for r in rows],
    }
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def parse_args(argv: list[str] | None, default_model: Callable[[], str] = tagger.model_name) -> Config:
    p = argparse.ArgumentParser(description="Run screenshots through the tagger and score the results.")
    p.add_argument("--images", type=Path, default=Path("eval/images"))
    p.add_argument("--labels", type=Path, default=Path("eval/labels.json"))
    p.add_argument("--sizes", default=f"{ORIGINAL},1600,1024",
                   help="comma list of 'original' or a longest edge in px")
    p.add_argument("--model", action="append", default=[], help="repeatable; default is GEMINI_MODEL")
    p.add_argument("--repeats", type=int, default=1, help="2 gives the noise floor")
    p.add_argument("--delay", type=float, default=5.0, help="seconds between calls")
    p.add_argument("--retries", type=int, default=2,
                   help="extra attempts after a 429 or 5xx (each is a real call)")
    p.add_argument("--retry-wait", type=float, default=20.0, help="seconds before a retry")
    p.add_argument("--only", action="append", default=[], help="repeatable file name filter")
    p.add_argument("--out", type=Path, default=Path("eval/results"))
    p.add_argument("--dry-run", action="store_true", help="prepare images and count calls, no API calls")
    args = p.parse_args(argv)
    sizes = [s.strip() for s in args.sizes.split(",") if s.strip()]
    if not sizes or any(s != ORIGINAL and not s.isdigit() for s in sizes):
        p.error("--sizes must be 'original' and/or pixel counts, e.g. original,1600,1024")
    if args.repeats < 1 or args.retries < 0:
        p.error("--repeats must be at least 1 and --retries at least 0")
    try:
        models = args.model or [default_model()]
    except RuntimeError:
        if not args.dry_run:
            raise
        models = ["(unset)"]  # a dry run needs no configuration
    return Config(args.images, args.labels, sizes, models, args.repeats, args.delay, args.only,
                  args.out, args.dry_run, args.retries, args.retry_wait)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    load_dotenv()
    try:
        run(parse_args(argv))
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        # RuntimeError text is only "GEMINI_API_KEY is not set" style. A labels
        # error (ValueError, which includes bad JSON) names the human's own file.
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
