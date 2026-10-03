# Full Plan: AI Screenshot Repository

> **Status: frozen baseline.** This is the original plan, written on 2026-10-03 before any code, and its wording is left as written. It says what we set out to build. What was actually built, with the evidence, is in [02-mvp-outcome.md](02-mvp-outcome.md). This file was renamed from `projectplan.md`; section numbers are unchanged, so older references to `projectplan.md` section N point here.
>
> Each item below carries a status tag: **[BUILT]** as planned, **[CHANGED]** built differently (see the note), **[CUT]** dropped for time, **[LATER]** not started.

## What changed since this plan was written
The project ran long, so phases 2 to 5 were combined into one pass and some features were cut. The changes that matter:
- **Cut for time:** category and place chips with `GET /api/facets` (F4, journey J3), the separate `/image/{id}` page, "Load more", toasts, per-card polling and the hold-out evaluation. Search plus clickable tags, in a detail dialog on the one page, cover the main journey.
- **The model is `gemini-3.1-flash-lite`,** chosen in the spike. `gemini-3.5-flash` allows only 20 requests per day on the free tier and returned 503 on about half of its early calls.
- **Demo and eval data is a synthetic set** (`eval/make_synthetic.py`), because it is public-safe and its labels are exact. The real photos stay local.
- **Tagging had to learn about quotas:** it retries only when Google suggests a short wait, and gives up on an image after a deadline, because the free tier's daily limits are small and per model.

Evidence: [spike-results.md](../spike-results.md). How it was built: [02-mvp-outcome.md](02-mvp-outcome.md).

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
| # | Feature | Behaviour | Status |
|---|---|---|---|
| F1 | Upload and compress | Drag and drop one or many images. Each is validated, re-encoded smaller, and deduplicated by hash. | **[BUILT]** Up to 20 files of 10 MB, validated by decoding, 1600 px WebP, SHA-256 dedupe |
| F2 | AI tagging | Gemini returns structured JSON: title, summary, category, city, country, up to 8 tags, extracted text, personal-info flag. | **[BUILT]** `gemini-3.1-flash-lite`, prompt `v1` |
| F3 | Search | One box over title, summary, tags, place and extracted text. | **[BUILT]** FTS5 prefix search, with tags and places ranked first |
| F4 | Groups | Category and place chips with counts. No manual folders. | **[CUT]** Search plus clickable tags replace it |
| F5 | Library and detail | Thumbnail grid and a detail view with all fields. | **[CHANGED]** A grid, with the detail in a dialog on the same page |
| F6 | Failure handling | Failed images show their error and can be retried or deleted. Upload failures notify immediately. | **[CHANGED]** Failed cards show the error with retry and delete. A status line replaces toasts |
| F7 | Personal-info flag | Flagged images are hidden by default, with a "show flagged" toggle. A second line of defence only: the flag is set after the image has been sent. | **[BUILT]** Hidden by default, with a Show flagged checkbox |
| F8 | Eval harness | One command runs labelled screenshots through the pipeline and reports tag quality. | **[BUILT]** `python -m eval.run_eval` |

[LATER] **Stretch:** S1 manual tag edit/remove. *Not started.*

[BUILT] **Out of scope for v1:** accounts, hosting, Telegram, semantic search, phone sync, video, mobile app, non-English screenshots. *Unchanged: all of these are still out of scope.*

## 4. Tech stack and architecture
| Piece | Choice | Why | Status |
|---|---|---|---|
| Language and server | Python 3.12+, FastAPI, Uvicorn | Quick to build, async-friendly, good Gemini SDK | **[BUILT]** |
| AI | `google-genai` SDK; model name from `GEMINI_MODEL` env var; structured output via a Pydantic schema | Model can be swapped or compared without code changes | **[BUILT]** Model: `gemini-3.1-flash-lite` |
| Image handling | Pillow | Validates, resizes, re-encodes | **[BUILT]** |
| Database | SQLite (stdlib `sqlite3`) with FTS5 | No server to run, keyword search covers "tokyo" | **[BUILT]** |
| Image storage | Compressed files in `data/images/` | Local and simple | **[BUILT]** |
| Frontend | One HTML page, vanilla JS, served by FastAPI | No build step, easy to read | **[BUILT]** |
| Tests | pytest, Gemini mocked | Run without an API key | **[BUILT]** 291 tests, no key needed |
| Config | `.env` (`GEMINI_API_KEY`, `GEMINI_MODEL`) plus `.env.example`; `.env` and `data/` git-ignored | No secrets in the repo | **[BUILT]** Plus an optional `DATA_DIR` |

**Request flow**
1. [BUILT] Browser sends a file to `POST /api/images`.
2. [BUILT] Server checks type by content, hashes the original bytes, and returns early if a duplicate.
3. [BUILT] Server compresses and saves the file, inserts a row as `pending`, and responds immediately.
4. [BUILT] A background task sends the stored image to Gemini and validates the JSON.
5. [BUILT] On success it writes fields, tags and the search entry (`tagged`). On failure it records the error (`failed`).
6. [CHANGED] The browser polls `GET /api/images` every 2 s and updates cards. *Built as: the page re-fetches the whole grid every 2 s while any card is pending, and only redraws it when something changed.*

[BUILT] **Compression.** Convert to RGB, scale so the longest edge is at most 1600 px (never upscale), save as WebP at quality about 80. These numbers are a starting point, tuned in the phase 1 spike. Re-encoding also strips EXIF metadata and rejects malformed images. The original is not kept, and that is a deliberate trade-off. *The spike locked these numbers: 1600 px, quality 80.*

[BUILT] **Tagger seam.** Tagging lives in one module with a single function: image in, validated tags out. Tests mock it, and a different provider can replace it later.

**Why not:** embeddings or a vector DB (extra moving parts, keyword search is enough for the main query), a JS framework (no build step needed), cloud storage or hosting (see Future work).

[BUILT] **Bind address:** `127.0.0.1` only.

## 5. Navigation and routes
**Pages**
| Route | Purpose | Status |
|---|---|---|
| `/` | Library: dropzone with privacy warning, search box, category/place chips, grid | **[CHANGED]** Dropzone, privacy note, search and grid built. Chips cut |
| `/image/{id}` | Detail: full image, all fields, retry and delete | **[CUT]** The detail is a dialog on `/` |

**API**
| Method and path | Purpose | Status |
|---|---|---|
| `POST /api/images` | Upload multiple files; returns each file's id, status, duplicate flag, or a per-file error | **[BUILT]** |
| `GET /api/images?q=&category=&city=&status=&show_flagged=` | Search and filter, paginated | **[CHANGED]** Takes `q`, `status`, `show_flagged` and `limit` (default 40, up to 100). No `category` or `city`, and no paging |
| `GET /api/images/{id}` | One record | **[BUILT]** |
| `GET /api/images/{id}/file` | Serve the stored image | **[BUILT]** |
| `POST /api/images/{id}/retag` | Run tagging again | **[BUILT]** |
| `DELETE /api/images/{id}` | Remove file, rows and search entry | **[BUILT]** |
| `GET /api/facets` | Category and place counts for the chips | **[CUT]** Chips were cut |

## 6. User journeys
- [BUILT] **J1: Add a batch.** Drag 10 screenshots in. Cards appear as pending and fill in as tagging finishes.
- [BUILT] **J2: Find one.** Type "tokyo". Results show. Open one to see the full record. *(The record opens in a dialog on the same page.)*
- [CUT] **J3: Browse by group.** Click Travel, then Kyoto. *(Search and clickable tags replace it.)*
- [CHANGED] **J4: Upload fails.** A wrong file type, an oversized file, or a network error shows an error toast immediately. Other files in the batch still upload. *(Built as a status line, not a toast.)*
- [CHANGED] **J5: Tagging fails.** A Gemini rate limit or bad response. The card shows failed with the error and a toast on the next poll. Retry works and other images are unaffected. *(Built as a status line on the next poll, not a toast.)*
- [BUILT] **J6: Flagged.** A screenshot containing personal info is flagged and hidden from the default view. The toggle reveals it.
- [BUILT] **J7: Duplicate.** The same file again shows "already in library". There is no second Gemini call.

## 7. Data behaviour
- [BUILT] **Status flow:** `pending` → `tagged` or `failed`. Retag moves it back to `pending`. On server start, rows left `pending` by an interrupted run are marked `failed` ("interrupted").
- [BUILT] **Dedupe:** SHA-256 of the original upload bytes, checked before compressing, saving, or calling Gemini.
- [BUILT] **Validation:** PNG, JPEG or WebP, verified by decoding with Pillow. Max 10 MB per file, 20 files per upload. Pillow's decompression-bomb guard stays on.
- [BUILT] **Storage:** `data/images/<sha256>.webp`. The uploaded filename is never used.
- [CHANGED] **Tagging:** background task, at most 3 concurrent Gemini calls, one retry with backoff on rate limits. Prompt rule: tag only what the image states or clearly shows. Place stays null if not stated. Output goes through a Pydantic model, and an out-of-list category falls back to `other`. *Built as: a dedicated 3-thread pool, up to two retries (after 5 s and 15 s) when Google suggests a wait of 30 s or less, and no retry once 50 s have passed for that image.*
- [BUILT] **Normalisation:** tags are lowercase, trimmed and de-duplicated. City and country are separate fields.
- [BUILT] **Language:** English only for v1. Screenshots in other languages are not evaluated, and results for them are undefined.
- [BUILT] **Reproducibility:** each record stores `model` and `prompt_version`.
- [BUILT] **Search:** each term is quoted so special characters can't break the query, and matches by prefix ("tok" finds tokyo). Multiple terms are AND. Tags, city and country rank above summary and extracted text. Empty query returns newest first.
- [BUILT] **Delete:** removes the file, the rows and the search entry.
- [BUILT] **Retag:** overwrites AI fields. If S1 is built, manual edits must survive a retag. *(S1 was not built, so there are no manual edits to protect.)*
- [BUILT] **Delete during tagging:** if an image is deleted while it's being tagged, the result is discarded. No tags or search entry are written.
- [CUT] **Facets:** `GET /api/facets` counts only tagged, unflagged images.
- [BUILT] **Messages:** upload rejections and tagging failures use the fixed messages in `planning/design/design.md` §6. Raw exception details go to the server console only.
- [BUILT] **Upload results** come back in the order the files were sent.
- [CHANGED] **Pages:** the server returns `index.html` for both `/` and `/image/{id}`. *Only `/` exists now.*

```sql
images(id, sha256 UNIQUE, file_path, created_at, status, error,
       title, summary, category, city, country, extracted_text,
       contains_personal_info, model, prompt_version)
tags(image_id, tag, PRIMARY KEY(image_id, tag))
image_fts(title, summary, tags, city, country, extracted_text)  -- FTS5
```

[BUILT] *Built as written, except that `images.id` is `AUTOINCREMENT`, so an id is never reused after a delete.*

## 8. Acceptance criteria
| ID | Criterion | Status |
|---|---|---|
| AC-1 | Uploading 5 valid images leaves each as `tagged` or `failed` within 60 s. None stay `pending`. | **[BUILT]** |
| AC-2 | The same file uploaded twice produces one row and one Gemini call. | **[BUILT]** |
| AC-3 | On the eval set, searching a place returns at least 80% of the screenshots of that place. Provisional until the phase 1 spike. | **[BUILT]** Provisional: the sample is small |
| AC-4 | Searching a distinctive word that appears only in a screenshot's text (not in its tags) finds that screenshot. | **[BUILT]** |
| AC-5 | A screenshot with no stated place has null city and country. | **[BUILT]** Checked by the eval and a live audit. No unit test, since it depends on the model |
| AC-6 | A wrong file type or an oversized file is rejected with an immediate, clear message and nothing is saved. | **[BUILT]** |
| AC-7 | When Gemini errors, the record is `failed` with the error shown. The app keeps working and retry works. | **[BUILT]** |
| AC-8 | Images flagged as containing personal info are hidden from the default view. | **[BUILT]** |
| AC-9 | Searches like `"`, `*` or `AND` return results or an empty list, never a 500. | **[BUILT]** |
| AC-10 | Delete removes the file, the rows and the search results. | **[BUILT]** |
| AC-11 | Unit tests pass without an API key (Gemini mocked). | **[BUILT]** |
| AC-12 | A fresh clone runs by following the README, using only `GEMINI_API_KEY`. | **[BUILT]** |
| AC-13 | Stored images have a longest edge of at most 1600 px and carry no EXIF data. | **[BUILT]** |
| AC-14 | One command runs the eval and prints the report. | **[BUILT]** |

Evidence for each criterion is in [02-mvp-outcome.md](02-mvp-outcome.md#acceptance-criteria-status-and-evidence).

**Eval: how we judge Gemini's tagging**
- [CHANGED] Test set: 15–20 English-language screenshots I collect, with hand-written expected city/country/category and a few search queries each. Only public-safe images are committed. *Built as: 7 synthetic phone screenshots with exact labels, plus 5 real photos with hand-written labels. The 15 to 20 set was not collected.*
- [BUILT] Measures: query recall (AC-3), false-place rate (images with no place that got one), category accuracy, personal-info flag hits.
- [CHANGED] Comparisons in the spike: original vs 1600 px vs 1024 px images, to check compression doesn't hurt tagging. Optionally two Gemini models, if time allows. *Built as: original vs 1600 px only, since 1024 px was dropped. Two other models were probed, not compared.*
- [BUILT] Real failures found are logged as they happen for the demo. *They are in [corrections.md](../corrections.md) and [spike-results.md](../spike-results.md).*

## 9. Implementation phases
| Phase | Work | Est. | Outcome |
|---|---|---|---|
| 0 | Planning docs, repo skeleton, `.env.example` | 30 min | **[BUILT]** Commits `3d9db04`, `32e3ca1` |
| 1 | **Tagging spike:** run the schema on the labelled screenshots at three image sizes, judge tag quality, lock prompt v1 and the compression setting | 60 min | **[BUILT]** Narrower than planned: 7 synthetic and 5 real images, original vs 1600 px. Locked prompt `v1`, 1600 px quality 80 and flash-lite. See [spike-results.md](../spike-results.md) |
| 2 | Compression, DB, FTS, upload and search endpoints, tests | 75 min | **[BUILT]** Combined with phase 4 in one pass |
| 3 | Library and detail UI, toasts, polling | 45 min | **[CHANGED]** One page with a detail dialog. No toasts, chips or per-card polling |
| 4 | Hardening: duplicates, failures, flag, input validation | 30 min | **[BUILT]** Merged into phase 2, plus fixes from a fresh-context review |
| 5 | Eval script, README, demo recording | 60 min | **[CHANGED]** Eval harness and README built. The demo recording is still to do |

Phase 1 comes first because everything depends on tag quality. If it fails, the approach changes before anything else is built.

Phases 2 to 5 were combined into one pass. See [02-mvp-outcome.md](02-mvp-outcome.md).

## 10. Future work
- [LATER] **Hosted version:** Vercel for the app, Supabase for Postgres and image storage, plus a login. Compression helps here, since compressed images sit well under Vercel's 4.5 MB request limit.
- [LATER] **Privacy:** Gemini paid tier, a stage-and-confirm review step before sending, and an Ollama tagger behind the tagger seam for private local use.
- [LATER] **Multilingual support:** Chinese and other non-English screenshots, which would need translated tags and CJK-aware search (FTS5's default tokenizer treats a run of Chinese characters as one token).
- [LATER] Manual tag editing, semantic search, Telegram intake.
- [LATER] **Quota-aware tagging** *(added after the build)*: free-tier limits are small and per model (20 requests per day on `gemini-3.5-flash`). A paid tier, or a queue that spreads calls over several days, would lift the cap.

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

**Resolved** (these were open when the plan was written)
1. Flagged images: **stored but hidden** by default, with a Show flagged checkbox. [BUILT]
2. A stage-and-confirm step before sending to Gemini: **not built**, as recommended. The dropzone warning is used instead. [LATER]
3. Which Gemini model to start with: **`gemini-3.1-flash-lite`**, decided in the spike. [BUILT]

**Made after this plan was written**
| Decision | Why |
|---|---|
| Cut for time: chips and facets, the detail page, "Load more", toasts, per-card polling, the hold-out evaluation | The project ran long. Search plus clickable tags cover the main journey, and all 14 acceptance criteria still hold |
| Demo and eval data is a synthetic set. Real photos stay local | Public-safe by construction, and the labels are exact |
| The model is `gemini-3.1-flash-lite` | 3 to 12 s per call and reliable. `gemini-3.5-flash` allows 20 requests per day on the free tier and returned 503 on about half of its early calls |
| A place is filled only when the text states it | AC-5. A landmark photo with no caption gets no city, though the name can appear in the title and tags. Tuned over three prompt drafts |
| Retry only when Google suggests a short wait | A daily quota says hours, so retrying only holds a tagging slot |
| Refuse changing requests that come from other sites | A page on another site could otherwise spend the Gemini quota through the browser |
