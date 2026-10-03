# MVP Outcome: phases 2 to 5, as built

> **Status: record.** What the combined phases 2 to 5 produced, where the build departed from the plan, and the evidence for each acceptance criterion. Written after the build, on 2026-10-03.
> - The plan this replaces, as it was approved before building, is kept in Git: [mvp.md at commit `e871b50`](https://github.com/Wei-Hui-Yuan/ai-screenshot-repository/blob/e871b50b63616c245c2ad897c8fd54d3951e0515/planning/phase_plans/mvp.md).
> - The original vision, with every phase and feature, is [01-full-plan.md](01-full-plan.md).

## In short
After the phase 1 spike locked the tagging setup, phases 2 to 5 were built as one pass: backend, one-page UI, README and demo data. **All 14 acceptance criteria are met.** 291 tests pass without an API key, and a live audit against real Gemini passed 48 of 48 checks. Still to do: the demo recording.

Some of the planned UI was deliberately **deferred**, not dropped. The aim of v1 is a proof of concept that Gemini's tags are good enough to search by, and the project ran long, so the more advanced browsing and feedback features were postponed to a later version. The table below lists them.

## Scope
| Deferred | Built instead |
|---|---|
| F4 category and place chips, `GET /api/facets`, journey J3 | The search box. Tags in the detail view are clickable and run a search |
| The `/image/{id}` page and back/forward-cache handling | A `<dialog>` detail view on the one page |
| "Load more" | The newest 40 |
| The toast stack and its cap rules | One status line and one error line |
| Per-card polling | The grid re-fetches every 2 s while a card is pending, and redraws only when something changed |
| Drag-over outline, `.heic` rule, hold-out evaluation, the 1024 px arm, repeats, comparing other models | Nothing |

**Kept:** upload many, dedupe, compress, background tagging, search, detail with retry and delete, the personal-info flag hidden by default, failure handling and the eval command. Journeys J1, J2 and J4 to J7 work.

## What was built
| File | Job |
|---|---|
| [`app/db.py`](../../app/db.py) | All SQL, as fixed strings with bound parameters. SQLite in WAL mode with one short-lived connection per call. Tables `images`, `tags` and FTS5 `image_fts` ranked with bm25 (tags, city and country above summary and text). `images.id` is `AUTOINCREMENT`, so an id is never reused |
| [`app/search.py`](../../app/search.py) | Turns typed text into quoted prefix terms ANDed together. Only letters and digits survive, so FTS5 syntax can't change the query |
| [`app/images.py`](../../app/images.py) | `check_upload` (decodes the image, PNG, JPEG or WebP only, 10 MB cap, pixel limit), `sha256`, `compress` (1600 px WebP, no EXIF) and `store` (`<sha256>.webp`, written atomically) |
| [`app/tagger.py`](../../app/tagger.py) | The only code that talks to Gemini. Prompt `v1`, no tools, 45 s timeout. Failures become `TaggingError` with fixed messages, and 429 or 5xx is flagged transient only when Google's suggested wait is 30 s or less |
| [`app/main.py`](../../app/main.py) | The routes. Tagging runs on its own 3-thread pool, retries a busy service up to twice (after 5 s and 15 s) within a 50 s deadline per image, and records only error types in logs. An Origin check refuses changing requests from other sites |
| [`app/static/index.html`](../../app/static/index.html) | One page, vanilla JS, `textContent` only. Grid with four card states, search, Show flagged, drag and drop, and the detail dialog |
| `eval/` | [`run_eval.py`](../../eval/run_eval.py) scores tagging against labels. [`make_synthetic.py`](../../eval/make_synthetic.py) and [`make_demo_images.py`](../../eval/make_demo_images.py) draw fake screenshots |

**Request flow, as built.** `POST /api/images` checks each file by decoding it, hashes it and returns early for a duplicate, then compresses, stores and inserts a `pending` row. A pool thread sends the stored image to Gemini, validates the JSON with Pydantic and writes `tagged` or `failed`. The page polls while anything is pending.

## How it went
| Step | Outcome | Commits |
|---|---|---|
| 1. Lock the spike | Prompt `v1` after three drafts, `gemini-3.1-flash-lite`, 1600 px quality 80, a 45 s timeout. [spike-results.md](../spike-results.md) | `e871b50` |
| 2. Backend | `db`, `search`, `images`, `main` and 278 tests. A live check against real Gemini | `81bc0ad` |
| 3. UI | One page, checked in a real browser, then fixed after a fresh-context review | `390df19` |
| 4. Docs and demo | README, handoff 03, corrections, session export | `011332e`, `d46cfa3` |
| After the plan | Photo-style demo images, `agents.md` brought up to date, dead code removed, a port 3000 preview config | `676a3b2`, `02a32b3`, `8baccb8`, `6f7633f` |

## Where the build departed from the approved plan
1. **The free-tier quota was a real constraint.** The plan said flash-lite "has not hit a quota yet". The first live run failed on all 7 uploads because `.env` still named `gemini-3.5-flash`, which allows 20 requests per day. The first retry logic then retried that daily quota pointlessly, so retries now depend on Google's suggested wait. Corrections #30 and #32.
2. **The prompt needed two more drafts, not one,** to stop landmark photos getting an invented city. Drafts 2 and 3 fixed Milan and the Arc de Triomphe.
3. **A fresh-context review found gaps the plan didn't anticipate:** tagging tasks that could starve the API of threads, an image left pending if a database write failed, a 500 on a huge id, no bound on AC-1's 60 s, a cross-site POST that could spend the quota, and UI races. All were fixed. Correction #33.
4. **The tests landed in different files:** `test_api.py` and `test_db.py` instead of the planned `test_upload.py` and `test_flow.py`, plus tests for the demo scripts.
5. **Photo-style demo images were added** so the library looks like a real one. They are drawn, not photographed, and their tags are marked `dummy-data`.
6. **The README was trimmed by the owner after the build** (`5de5e3f`). The list of deferred features and the spike summary now live only in `planning/`.

## Acceptance criteria: status and evidence
| AC | Status | Evidence |
|---|---|---|
| AC-1 five images settle within 60 s | Met | `test_five_uploads_all_end_up_tagged_and_none_stay_pending`. Live audit: 7 tagged in 9 s. `test_a_busy_service_is_not_retried_once_the_deadline_has_passed` bounds the retries |
| AC-2 one row, one Gemini call | Met | `test_the_same_file_twice_is_one_row_and_one_gemini_call`. Live audit: a repeat upload is "already in library" |
| AC-3 place recall at least 80% | Met, provisional | Spike gate G3 and the live audit: every place query found its screenshot. The sample is small |
| AC-4 a word only in the text finds it | Met | `test_a_word_that_is_only_in_the_text_finds_the_screenshot`. Live audit: `48213` and `mascarpone` |
| AC-5 no stated place gives null | Met | Spike gate G1: 0 invented places on 6 synthetic no-place images, and the two real landmark photos after draft 3. No unit test, since it depends on the model |
| AC-6 bad files rejected, nothing saved | Met | `test_bad_files_are_rejected_with_a_fixed_message_and_nothing_is_saved`, `test_a_decompression_bomb_is_unreadable`, and the other `check_upload` tests |
| AC-7 failures shown, retry works | Met | `test_a_gemini_failure_marks_only_that_image_failed_and_retry_fixes_it`. A real quota failure was also seen in the live app |
| AC-8 flagged images hidden | Met | `test_a_personal_info_image_is_hidden_until_asked_for`, the live audit and the browser checks |
| AC-9 odd searches never give a 500 | Met | `test_odd_searches_give_results_or_an_empty_list_never_an_error`, `test_search.py` and a live check |
| AC-10 delete removes everything | Met | `test_delete_removes_the_file_the_rows_and_the_search_results` and `test_an_image_deleted_while_it_is_being_tagged_gets_no_tags_and_no_search_entry` |
| AC-11 tests pass without a key | Met | 291 pass. `tests/conftest.py` removes any key, and Gemini is mocked at `app.main.tag_image` |
| AC-12 a fresh clone runs | Met | Fresh clone and fresh venv: install, `pip check`, 278 tests, and the server starting with no `.env` |
| AC-13 at most 1600 px, no EXIF | Met | `test_stored_images_are_small_webp_and_the_original_is_not_kept` and the `compress` tests. Live audit: a stored 739 x 1600 WebP |
| AC-14 one command runs the eval | Met | `python -m eval.run_eval`, covered by `tests/test_run_eval.py` |

## What was verified, and how
- **Tests:** 291 pass with `pytest -W error` and no key. Gemini is always mocked.
- **Tests that can fail:** more than 40 deliberate bugs were injected one at a time, and every one is now caught by a test. Several tests that had passed by accident were fixed along the way.
- **Live audit:** 48 of 48 checks against the running app with real Gemini and the owner's real `.env`, plus browser checks of the grid, search, detail, flagged toggle and uploads.
- **Fresh clone:** a new clone with a new venv and no `.env`.
- **Rules:** no `innerHTML`, no string-built SQL, the server listens on `127.0.0.1` only, and the API key appears in no commit or file.
- **Mistakes:** 33 corrections are logged and confirmed in [corrections.md](../corrections.md).

## Limits and open items
- **The evidence is small.** The prompt was tuned on 7 synthetic and 5 real images, so the numbers are "tuned-on". The owner also reports that real Instagram images and personal photos tagged successfully. That is informal and was not scored.
- **The free tier is small and uneven.** Limits are per model and not published. `gemini-3.5-flash` allows 20 requests per day, while flash-lite handled about 50 calls in a day.
- **Not tested:** a re-upload racing a delete, heavy load, and the Windows locked-file delete in real use.
- **Still to do:** the demo recording.
- **Future work:** the deferred UI features in the Scope table (chips, "Load more", a separate detail page, toasts, per-card polling, the drag-over outline). [design.md](../design/design.md) keeps their designs, each with a "Designed but not built" note giving the reasoning.
