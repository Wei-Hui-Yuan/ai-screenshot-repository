# Project Plan: AI Screenshot Repository

> **MVP scope (2026-10-03).** v1 was cut for time. See `planning/phase_plans/mvp.md`. **Cut:** category and place chips and `GET /api/facets` (F4, journey J3), the `/image/{id}` page (the detail view is a dialog on `/`), "Load more" (newest 40), toasts, per-card polling, the hold-out evaluation. **Changed:** the model is `gemini-3.1-flash-lite`, and demo and eval data is the synthetic set from `eval/make_synthetic.py`. The free tier allows 20 requests per day per model (`planning/spike-results.md`). The sections below describe the original scope.

## 1. Product overview
**Problem.** I screenshot things to remember them (places, food, recipes, articles, receipts) and then can't find them again. Many are social-media posts that can't be fetched through any API, so the screenshot is the only copy.

**Solution.** Drop screenshots into a local web app. Gemini reads each one and tags it. Typing "tokyo" returns every screenshot about Tokyo.

**What this version is for.** v1 is local-first and answers one question: **how well can Gemini tag real screenshots well enough to search by?** The eval is as important as the app.

**Success looks like:** finding a saved screenshot with one word in under 10 seconds, and a measured answer on tag quality.

**Origin.** This started as an AI travel-review aggregator, which was dropped because the platforms offer no usable API access. The screenshots I'd already collected turned out to be the real problem.

## 2. Who the hub serves
- **Primary:** one person on one machine, saving phone screenshots in batches. English-language content only. Hundreds of images, not millions.
- **Secondary:** reviewers who run it from a fresh clone with only a Gemini API key.
- **Not served:** teams, multi-user access, cloud sync, anyone needing exact OCR, non-English content.
- **Privacy stance:** images are sent to Gemini's free tier, which may use inputs to improve Google's products. Only non-sensitive screenshots should be uploaded. The app warns on the dropzone and in the README.

## 3. Core features
| # | Feature | Behaviour |
|---|---|---|
| F1 | Upload and compress | Drag and drop one or many images. Each is validated, re-encoded smaller, and deduplicated by hash. |
| F2 | AI tagging | Gemini returns structured JSON: title, summary, category, city, country, up to 8 tags, extracted text, personal-info flag. |
| F3 | Search | One box over title, summary, tags, place and extracted text. |
| F4 | Groups | Category and place chips with counts. No manual folders. |
| F5 | Library and detail | Thumbnail grid and a detail view with all fields. |
| F6 | Failure handling | Failed images show their error and can be retried or deleted. Upload failures notify immediately. |
| F7 | Personal-info flag | Flagged images are hidden by default, with a "show flagged" toggle. A second line of defence only: the flag is set after the image has been sent. |
| F8 | Eval harness | One command runs labelled screenshots through the pipeline and reports tag quality. |

**Stretch:** S1 manual tag edit/remove.

**Out of scope for v1:** accounts, hosting, Telegram, semantic search, phone sync, video, mobile app, non-English screenshots.

## 4. Tech stack and architecture
| Piece | Choice | Why |
|---|---|---|
| Language and server | Python 3.12+, FastAPI, Uvicorn | Quick to build, async-friendly, good Gemini SDK |
| AI | `google-genai` SDK; model name from `GEMINI_MODEL` env var; structured output via a Pydantic schema | Model can be swapped or compared without code changes |
| Image handling | Pillow | Validates, resizes, re-encodes |
| Database | SQLite (stdlib `sqlite3`) with FTS5 | No server to run, keyword search covers "tokyo" |
| Image storage | Compressed files in `data/images/` | Local and simple |
| Frontend | One HTML page, vanilla JS, served by FastAPI | No build step, easy to read |
| Tests | pytest, Gemini mocked | Run without an API key |
| Config | `.env` (`GEMINI_API_KEY`, `GEMINI_MODEL`) plus `.env.example`; `.env` and `data/` git-ignored | No secrets in the repo |

**Request flow**
1. Browser sends a file to `POST /api/images`.
2. Server checks type by content, hashes the original bytes, and returns early if a duplicate.
3. Server compresses and saves the file, inserts a row as `pending`, and responds immediately.
4. A background task sends the stored image to Gemini and validates the JSON.
5. On success it writes fields, tags and the search entry (`tagged`). On failure it records the error (`failed`).
6. The browser polls `GET /api/images` every 2 s and updates cards.

**Compression.** Convert to RGB, scale so the longest edge is at most 1600 px (never upscale), save as WebP at quality about 80. These numbers are a starting point, tuned in the phase 1 spike. Re-encoding also strips EXIF metadata and rejects malformed images. The original is not kept, and that is a deliberate trade-off.

**Tagger seam.** Tagging lives in one module with a single function: image in, validated tags out. Tests mock it, and a different provider can replace it later.

**Why not:** embeddings or a vector DB (extra moving parts, keyword search is enough for the main query), a JS framework (no build step needed), cloud storage or hosting (see Future work).

**Bind address:** `127.0.0.1` only.

## 5. Navigation and routes
**Pages**
| Route | Purpose |
|---|---|
| `/` | Library: dropzone with privacy warning, search box, category/place chips, grid |
| `/image/{id}` | Detail: full image, all fields, retry and delete |

**API**
| Method and path | Purpose |
|---|---|
| `POST /api/images` | Upload multiple files; returns each file's id, status, duplicate flag, or a per-file error |
| `GET /api/images?q=&category=&city=&status=&show_flagged=` | Search and filter, paginated |
| `GET /api/images/{id}` | One record |
| `GET /api/images/{id}/file` | Serve the stored image |
| `POST /api/images/{id}/retag` | Run tagging again |
| `DELETE /api/images/{id}` | Remove file, rows and search entry |
| `GET /api/facets` | Category and place counts for the chips |

## 6. User journeys
- **J1: Add a batch.** Drag 10 screenshots in. Cards appear as pending and fill in as tagging finishes.
- **J2: Find one.** Type "tokyo". Results show. Open one to see the full record.
- **J3: Browse by group.** Click Travel, then Kyoto.
- **J4: Upload fails.** A wrong file type, an oversized file, or a network error shows an error toast immediately. Other files in the batch still upload.
- **J5: Tagging fails.** A Gemini rate limit or bad response. The card shows failed with the error and a toast on the next poll. Retry works and other images are unaffected.
- **J6: Flagged.** A screenshot containing personal info is flagged and hidden from the default view. The toggle reveals it.
- **J7: Duplicate.** The same file again shows "already in library". There is no second Gemini call.

## 7. Data behaviour
- **Status flow:** `pending` → `tagged` or `failed`. Retag moves it back to `pending`. On server start, rows left `pending` by an interrupted run are marked `failed` ("interrupted").
- **Dedupe:** SHA-256 of the original upload bytes, checked before compressing, saving, or calling Gemini.
- **Validation:** PNG, JPEG or WebP, verified by decoding with Pillow. Max 10 MB per file, 20 files per upload. Pillow's decompression-bomb guard stays on.
- **Storage:** `data/images/<sha256>.webp`. The uploaded filename is never used.
- **Tagging:** background task, at most 3 concurrent Gemini calls, one retry with backoff on rate limits. Prompt rule: tag only what the image states or clearly shows. Place stays null if not stated. Output goes through a Pydantic model, and an out-of-list category falls back to `other`.
- **Normalisation:** tags are lowercase, trimmed and de-duplicated. City and country are separate fields.
- **Language:** English only for v1. Screenshots in other languages are not evaluated, and results for them are undefined.
- **Reproducibility:** each record stores `model` and `prompt_version`.
- **Search:** each term is quoted so special characters can't break the query, and matches by prefix ("tok" finds tokyo). Multiple terms are AND. Tags, city and country rank above summary and extracted text. Empty query returns newest first.
- **Delete:** removes the file, the rows and the search entry.
- **Retag:** overwrites AI fields. If S1 is built, manual edits must survive a retag.
- **Delete during tagging:** if an image is deleted while it's being tagged, the result is discarded. No tags or search entry are written.
- **Facets:** `GET /api/facets` counts only tagged, unflagged images.
- **Messages:** upload rejections and tagging failures use the fixed messages in `planning/design/design.md` §6. Raw exception details go to the server console only.
- **Upload results** come back in the order the files were sent.
- **Pages:** the server returns `index.html` for both `/` and `/image/{id}`.

```sql
images(id, sha256 UNIQUE, file_path, created_at, status, error,
       title, summary, category, city, country, extracted_text,
       contains_personal_info, model, prompt_version)
tags(image_id, tag, PRIMARY KEY(image_id, tag))
image_fts(title, summary, tags, city, country, extracted_text)  -- FTS5
```

## 8. Acceptance criteria
| ID | Criterion |
|---|---|
| AC-1 | Uploading 5 valid images leaves each as `tagged` or `failed` within 60 s. None stay `pending`. |
| AC-2 | The same file uploaded twice produces one row and one Gemini call. |
| AC-3 | On the eval set, searching a place returns at least 80% of the screenshots of that place. Provisional until the phase 1 spike. |
| AC-4 | Searching a distinctive word that appears only in a screenshot's text (not in its tags) finds that screenshot. |
| AC-5 | A screenshot with no stated place has null city and country. |
| AC-6 | A wrong file type or an oversized file is rejected with an immediate, clear message and nothing is saved. |
| AC-7 | When Gemini errors, the record is `failed` with the error shown. The app keeps working and retry works. |
| AC-8 | Images flagged as containing personal info are hidden from the default view. |
| AC-9 | Searches like `"`, `*` or `AND` return results or an empty list, never a 500. |
| AC-10 | Delete removes the file, the rows and the search results. |
| AC-11 | Unit tests pass without an API key (Gemini mocked). |
| AC-12 | A fresh clone runs by following the README, using only `GEMINI_API_KEY`. |
| AC-13 | Stored images have a longest edge of at most 1600 px and carry no EXIF data. |
| AC-14 | One command runs the eval and prints the report. |

**Eval: how we judge Gemini's tagging**
- Test set: 15–20 English-language screenshots I collect, with hand-written expected city/country/category and a few search queries each. Only public-safe images are committed.
- Measures: query recall (AC-3), false-place rate (images with no place that got one), category accuracy, personal-info flag hits.
- Comparisons in the spike: original vs 1600 px vs 1024 px images, to check compression doesn't hurt tagging. Optionally two Gemini models, if time allows.
- Real failures found are logged as they happen for the demo.

## 9. Implementation phases
| Phase | Work | Est. |
|---|---|---|
| 0 | Planning docs, repo skeleton, `.env.example` | 30 min |
| 1 | **Tagging spike:** run the schema on the labelled screenshots at three image sizes, judge tag quality, lock prompt v1 and the compression setting | 60 min |
| 2 | Compression, DB, FTS, upload and search endpoints, tests | 75 min |
| 3 | Library and detail UI, toasts, polling | 45 min |
| 4 | Hardening: duplicates, failures, flag, input validation | 30 min |
| 5 | Eval script, README, demo recording | 60 min |

Phase 1 comes first because everything depends on tag quality. If it fails, the approach changes before anything else is built.

## 10. Future work
- **Hosted version:** Vercel for the app, Supabase for Postgres and image storage, plus a login. Compression helps here, since compressed images sit well under Vercel's 4.5 MB request limit.
- **Privacy:** Gemini paid tier, a stage-and-confirm review step before sending, and an Ollama tagger behind the tagger seam for private local use.
- **Multilingual support:** Chinese and other non-English screenshots, which would need translated tags and CJK-aware search (FTS5's default tokenizer treats a run of Chinese characters as one token).
- Manual tag editing, semantic search, Telegram intake.

## 11. Decisions
**Made**
| Decision | Why |
|---|---|
| Drag and drop only; Telegram cut | Setup cost, not the core problem |
| Gemini free tier, non-sensitive screenshots only | Goal is to evaluate Gemini's tagging. Privacy is handled by what I upload plus app warnings |
| Local stack for v1; Vercel and Supabase later | Faster to build and test tagging quality first |
| Compress and store images; originals not kept | Smaller storage, smaller Gemini payload, easier hosting later |
| Background tagging with polling; upload errors notify immediately | Users keep using the app while tagging runs |
| English-only content for v1 | Removes translation and search-tokenizer complexity, keeps the eval focused on tagging quality |
| I collect the test screenshots | They have to be real, and mine |
| Name: AI Screenshot Repository | |

**Open**
1. Flagged images: store but hide (draft default), or refuse to store? *(to be answered separately)*
2. Add a stage-and-confirm step before sending to Gemini? Recommendation: not in v1. Use the dropzone warning instead.
3. Which Gemini model to start with? Decided in the phase 1 spike.
