# Plan: MVP for phases 2–5 (cut for speed, fake images)

## Context
Phase 1 is about 90% done. We have the tagger, `compress()`, the schema and an eval harness, all tested (159 tests). The project is running long, so you asked to cut scope and to use **fake images** to prove the idea. This plan merges phases 2–5 into one pass, approved once.

**Why this is safe:** the assessment values judgment and process over size ("2–3 hours is acceptable"). Every acceptance criterion except AC-3's size stays; only features outside the ACs are cut.

**What the spike found (decides the plan):**
- `gemini-3.1-flash-lite` works well: 4–12 s per call, G1–G5 all PASS on the synthetic set, the injection image was resisted and the personal-info flag fires. It has not hit a quota yet (18 calls today).
- `gemini-3.5-flash` allows only **20 requests/day on the free tier**, and 503s hit half its calls. `gemini-3.8-flash` returned a 503 on its one probe.
- On real photos, flash-lite filled Milan, Italy and Paris, France from landmarks that no text states (G1 fails there). One prompt tweak should fix that.
- Compression (original vs 1600 px WebP q80) cost nothing measurable.

## Decisions (yours, from this conversation)
Cut as proposed; **demo and eval data is the synthetic set** (`eval/make_synthetic.py`). Your real photos stay local and untracked. Model: `gemini-3.1-flash-lite`, kept swappable through `GEMINI_MODEL`.

## What gets cut
| Cut | Replaced by |
|---|---|
| F4 category and place chips, `/api/facets`, journey **J3** | Search box only. Tags in the detail view are clickable and run a search |
| `/image/{id}` route, back/forward-cache handling | A `<dialog>` detail view on the one page |
| Load more | Newest 40 |
| Toast stack and cap rules | One `role="status"` line and inline errors |
| Per-card polling | Re-fetch the grid every 2 s while any card is pending |
| Drag-over outline, `.heic` rule, hold-out evaluation, 1024 arm, repeats, other-model runs | Nothing |
| Extra reviews and per-step plans | One fresh-context review after the UI; commits per phase |

Kept: upload many, dedupe, compress, background tagging, search, detail with retry and delete, personal-info flag hidden by default, failure handling, the eval command. That covers **all 14 ACs** and journeys J1, J2, J4–J7.

## Step 1: finish and lock the spike (~8 real calls)
- Prompt `v1-draft2`: one rule rewritten so a landmark, building or scene never counts as a stated place, and a city alone is fine.
- `eval/make_synthetic.py`: add one image, a travel post that mentions the Eiffel Tower without naming a city (label: no place). It reproduces the G1 failure on fake data. The form fix is already in the working tree.
- Run flash-lite on the 7 synthetic images at 1600 px. If G1–G5 pass, lock prompt `v1`, compression 1600 / q80, request timeout (from measured latencies, about 45 s), and `.env.example` model. If not, one more tweak, then lock anyway and record the gap.
- Write a short `planning/spike-results.md`: the tables, the quota and 503 findings, and the limits (small n, mostly photos in the first runs).
- **Commit 1.**

## Step 2: backend (phase 2 and 4 merged)
New and changed files, reusing what exists:
- `app/db.py`: all SQL, parameterised, `sqlite3`, WAL mode. Tables per projectplan §7 (`images`, `tags`, `image_fts` with bm25 column weights so tags, city and country rank above summary and text). Functions: `init_db`, `add_pending` (UNIQUE sha, so duplicates are detected), `set_tagged` (returns False if the row was deleted, so the result is discarded), `set_failed`, `reset_pending`, `mark_interrupted` (startup: pending becomes failed), `list_images`, `get_image`, `delete_image`.
- `app/search.py`: `match_query(q)`: split into words, quote each, prefix match (`"tok"*`), AND. Returns `None` for an empty query. Covers AC-9 (`"`, `*`, `AND` can't break it).
- `app/images.py` (extend): `validate` (decode with Pillow, PNG/JPEG/WebP only, 10 MB cap, decompression-bomb guard left on), `sha256`, `store` (`data/images/<sha>.webp`, using the existing `compress`).
- `app/tagger.py` (small change): `TaggingError.transient` (429 or 5xx), so `main.py` can retry without importing the SDK.
- `app/main.py`: endpoints from projectplan §5 minus facets and `/image/{id}`: `POST /api/images` (max 20, per-file result in send order with the fixed messages, filenames never used), `GET /api/images?q=&status=&show_flagged=`, `GET /api/images/{id}`, `GET /api/images/{id}/file`, `POST /api/images/{id}/retag`, `DELETE /api/images/{id}`, plus `/`. Background tagging with at most 3 concurrent calls, up to 2 retries with backoff on transient errors, and raw causes logged by type only.
- Tests (Gemini mocked at `app.main.tag_image`): `test_db.py`, `test_search.py`, `test_upload.py`, `test_flow.py` covering AC-1, 2, 5–10 and the startup "interrupted" rule.

## Step 3: UI (phase 3)
One `app/static/index.html`, vanilla JS, no build step, **`textContent` only** (rule 11). Colour tokens from `design.md` §2 (light and dark). Layout: header with the privacy note, "Add screenshots" button plus page-wide drop, search box (250 ms debounce), "Show flagged" checkbox, a grid of 3:4 cards in the four states, and a `<dialog>` detail view (image, title, place and category, summary, clickable tags, "Text in image" disclosure, Retry, Delete with `confirm()`).
**Commit 3 after a fresh-context review of steps 2 and 3 together.**

## Step 4: docs and demo (phase 5)
- Run `python -m eval.run_eval` once on the synthetic set with the final prompt and record the result. The harness already exists (AC-14).
- `README.md`: what it is, how to run it (AC-12), the trade-offs, and honest limits: free-tier quotas and 503s, English only, local only, Google may use free-tier inputs, Gemini's `generate_content` is labelled legacy, 20 requests/day on 3.5-flash.
- Add a short "MVP scope" banner to `projectplan.md` and `design.md` listing what was cut. **I'll make these small edits only with your approval of this plan**, since they're your documents.
- Handoff 03, corrections, and the session-log export.

## Rough time (my estimates, not measured)
Step 1 about 20 min, step 2 about 60–75 min, step 3 about 45 min, step 4 about 45 min: roughly 3 hours, down from the original plan's remaining phases.

## Verification
- `pytest -W error` in the venv with no key; fresh-clone check at the end (AC-11, AC-12).
- Live end-to-end: start the server (`.claude/launch.json`), upload the 7 synthetic screenshots by API with the real key (7 calls), then in the browser pane: cards go pending to tagged, search "kyoto", "pasta" and the text-only "48213" each find the right card, the personal-info form is hidden until "Show flagged", delete removes it, a corrupt file is rejected, and a duplicate says "already in library". The browser pane has no file picker, so uploads go through the API and the page is checked by reading and screenshots. You can drag the images in by hand for the demo.
- Rule checks by grep: no `innerHTML`, no f-string SQL, server bound to `127.0.0.1`, nothing from `.env` or `data/` staged.
- Honest limits: the fake set is clean and English, so it flatters the model. Real-world tagging quality is only anecdotally checked on your 5 real photos.
