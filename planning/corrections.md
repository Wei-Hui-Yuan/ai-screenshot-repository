# Corrections Log

Every time the AI gets something wrong, whoever catches it, it goes here. Rules are in `planning/agents/agents.md` section 7.

**Human verdict:** every entry starts as `Pending`. Only the human changes it, to `Confirmed` or `Rejected: <reason>`. A fix isn't a correction until the human confirms it's right.

> **Condensed.** Entries #1 to #33 were shortened after the human had confirmed them, and the verdicts were given on the original wording. Numbers, dates, phases, who or what caught each mistake, and the verdicts are unchanged. The long form of every entry is in Git: [corrections.md before condensing](https://github.com/Wei-Hui-Yuan/ai-screenshot-repository/blob/6f7633fc73cfb942b0a273e954b4fb32c0b8bf1e/planning/corrections.md).

### #1 · Planning · 2026-10-03
- **What the AI got wrong:** Proposed 12 project ideas as solutions before understanding the user's actual problems.
- **Caught by:** Human, who rejected all 12 and asked for a problem-solving approach.
- **Fix / lesson:** Switched to problem-first discovery, which led to the screenshot problem.
- **Human verdict:** Confirmed

### #2 · Planning · 2026-10-03
- **What the AI got wrong:** Presented the `sensitive` flag as a privacy protection, but Gemini sets it after the image has been sent.
- **Caught by:** AI, while checking Google's Gemini API terms.
- **Fix / lesson:** Renamed to `contains_personal_info`, a second line of defence. Privacy relies on non-sensitive uploads plus a dropzone warning.
- **Human verdict:** Confirmed

### #3 · Planning · 2026-10-03
- **What the AI got wrong:** The first plan draft referenced `decisions.md`, a file that didn't exist.
- **Caught by:** AI, self-review of the draft.
- **Fix / lesson:** Moved the decision log into section 11 of the project plan.
- **Human verdict:** Confirmed

### #4 · Planning · 2026-10-03
- **What the AI got wrong:** The corrections rule in `agents.md` let the AI log its own fixes without human sign-off.
- **Caught by:** Human, who pointed out that the human must confirm each correction.
- **Fix / lesson:** Added a Human verdict. Entries start `Pending` and only the human changes it.
- **Human verdict:** Confirmed

### #5 · Planning (design) · 2026-10-03
- **What the AI got wrong:** Claimed text contrast met WCAG AA, but two light-theme pairs failed: `--muted` on `--surface` (4.40:1) and `--danger` on `--surface` (4.43:1).
- **Caught by:** AI, via a fresh-context accessibility reviewer (subagent), then re-checked with a script.
- **Fix / lesson:** Darkened light `--muted` and `--danger` and added `--border-strong`. All 30 pairs pass. Compute contrast, don't assert it.
- **Human verdict:** Confirmed

### #6 · Planning (design) · 2026-10-03
- **What the AI got wrong:** Polled only while a visible card was pending, so with a search active new uploads never showed, the failure toast never fired (J1, J5) and newly flagged images stayed visible (AC-8).
- **Caught by:** AI, via completeness and scope reviewers (subagents).
- **Fix / lesson:** Track pending IDs, poll `status=pending`, replace cards one at a time, remove newly flagged cards with a toast, clear filters after an upload.
- **Human verdict:** Confirmed

### #7 · Planning (design) · 2026-10-03
- **What the AI got wrong:** Over-scoped the UI: a "Show flagged (3)" count no endpoint could supply, and about 15 behaviours (estimated 80–100 min) for a 45-minute phase, with no priorities.
- **Caught by:** AI, via scope and completeness reviewers (subagents).
- **Fix / lesson:** Plain checkbox, no count. Cut the pulse animation, `/` shortcut, drop overlay, delete toast and duplicate retry button. Added a build order and cut list.
- **Human verdict:** Confirmed

### #8 · Planning (design) · 2026-10-03
- **What the AI got wrong:** Never said how one HTML file serves two routes, which would push an implementer toward a client-side router outside the plan.
- **Caught by:** AI, via the scope reviewer (subagent). The completeness reviewer flagged it too.
- **Fix / lesson:** Full page loads through real links, `index.html` served for both routes, URL query keys matching the API's.
- **Human verdict:** Confirmed

### #9 · Planning (design) · 2026-10-03
- **What the AI got wrong:** Assumed every Back was a fresh load and used `history.back()` for "← Library". Browsers restore pages from the back/forward cache, so after Retry or Delete the old page would return stale (J5, AC-8), and the link did nothing in a new tab.
- **Caught by:** AI, via a second-round regression reviewer (subagent).
- **Fix / lesson:** Views reload on `pageshow` from the cache. "← Library" is a real link plus the saved query, and Delete uses `location.replace`.
- **Human verdict:** Confirmed

### #10 · Planning (design) · 2026-10-03
- **What the AI got wrong:** Toast rules contradicted each other: the 3-toast cap could remove error toasts, each failed image fired its own toast, and "Uploading..." had a 5 s timer. Rejection messages were undefined, so raw exception text could reach the user (AC-6).
- **Caught by:** AI, via a second-round regression reviewer (subagent).
- **Fix / lesson:** One grouped toast per poll, a cap that keeps errors, no timer on "Uploading...", and fixed server messages.
- **Human verdict:** Confirmed

### #11 · Planning (design) · 2026-10-03
- **What the AI got wrong:** The design never said server data must be shown as plain text, so text Gemini extracts could run as script (stored XSS).
- **Caught by:** AI, while fixing how file names appear in the upload summary.
- **Fix / lesson:** Added "Data is text, never HTML" (`textContent`, `encodeURIComponent`) and proposed it as a hard rule in `agents.md`.
- **Human verdict:** Confirmed

### #12 · Phase 0 (plan) · 2026-10-03
- **What the AI got wrong:** Named `httpx` from memory as what TestClient needs. A fresh install resolves to Starlette 1.7.0, whose TestClient imports `httpx2` and falls back to `httpx` only with a deprecation warning.
- **Caught by:** AI, via a fresh-context plan reviewer (subagent), confirmed in Starlette's source and PyPI metadata.
- **Fix / lesson:** `requirements.txt` uses `httpx2` and pins `starlette==1.7.0`. Check dependency claims against the installed version, not memory.
- **Human verdict:** Confirmed

### #13 · Phase 0 (plan) · 2026-10-03
- **What the AI got wrong:** Used `git check-ignore -v` to show `.env.example` isn't ignored, but `-v` prints a `!` negation match and exits 0, so it would look ignored.
- **Caught by:** AI, via the plan reviewer (subagent).
- **Fix / lesson:** Ignored paths are checked with `-v`. Paths that must not be ignored are checked without it, expecting no output and exit 1.
- **Human verdict:** Confirmed

### #14 · Phase 0 (plan) · 2026-10-03
- **What the AI got wrong:** Checks ran bare `pip`, `pytest` and `uvicorn`, but global Python already has fastapi, uvicorn, pytest and watchfiles, so a check could pass falsely and hide the reloader scanning `.venv`.
- **Caught by:** AI, via the plan reviewer (subagent), confirmed with `pip list`.
- **Fix / lesson:** Every check runs through `.venv\Scripts\python.exe -m ...`, and the §2 command is checked after activation.
- **Human verdict:** Confirmed

### #15 · Phase 0 (plan) · 2026-10-03
- **What the AI got wrong:** The plan existed only in `~/.claude/plans`, but the assessment brief requires agent plans in `planning/`.
- **Caught by:** AI, via the plan reviewer (subagent).
- **Fix / lesson:** Saved as `planning/phase_plans/phase-0.md`.
- **Human verdict:** Confirmed

### #16 · Phase 0 · 2026-10-03
- **What the AI got wrong:** `.gitignore` used `data/`, which matches at any depth, so a future `tests/data/` or `eval/data/` would silently drop out of git and break a fresh clone (AC-12). The AI's own check only tried root-level paths.
- **Caught by:** AI, via an end-of-phase reviewer (subagent), using `git check-ignore --no-index`.
- **Fix / lesson:** Changed to `/data/` and re-checked nested and root paths. Test ignore rules with paths that should not match, too.
- **Human verdict:** Confirmed

### #17 · Phase 1 (plan) · 2026-10-03
- **What the AI got wrong:** `TagResult` didn't guard against Pydantic's error text: `str(ValidationError)` echoes part of the input, so a truncated Gemini reply would put screenshot text in an error message (hard rule 2).
- **Caught by:** AI, via the plan reviewer (subagent), re-tested with a synthetic string.
- **Fix / lesson:** `ConfigDict(hide_input_in_errors=True)`. The harness records only the error type, `kind` and finish reason, never `str(e)`, and a test asserts a bad value never appears in an error.
- **Human verdict:** Confirmed

### #18 · Phase 1 (plan) · 2026-10-03
- **What the AI got wrong:** SDK exceptions could escape `tagger.py`, and nothing guarded `response.text` being `None` (blocked prompt, SAFETY stop) or truncated JSON from MAX_TOKENS. Only `tagger.py` may import the SDK, so phase 2 couldn't handle these or show the fixed §6 messages (AC-7).
- **Caught by:** AI, via the plan reviewer (subagent).
- **Fix / lesson:** `tagger.py` raises `TaggingError(kind, finish_reason)` with fixed messages and a bounded `max_output_tokens`. A fake-client test covers empty, blocked, MAX_TOKENS, 429, timeout and invalid JSON.
- **Human verdict:** Confirmed

### #19 · Phase 1 (plan) · 2026-10-03
- **What the AI got wrong:** "Verified facts" passed off a docs summariser's output as verified (model ids, thinking defaults, an image-token rule), including a model id the SDK doesn't list. The "empty API key" blocker was a snapshot from before the human saved `.env`.
- **Caught by:** AI, via the plan reviewer (subagent), re-checked against the SDK and `.env`.
- **Fix / lesson:** Facts split into source-verified and summariser-sourced; the token claim and unlisted model dropped; the blocker reported as stale. Say how each fact was checked, and re-check state before reporting a blocker.
- **Human verdict:** Confirmed

### #20 · Phase 1 (plan) · 2026-10-03
- **What the AI got wrong:** Tuned the prompt and judged results on the same ~5 images, set no pass/fail thresholds beforehand, had no noise floor and recorded no token counts, so the numbers would look better than they are.
- **Caught by:** AI, via the plan reviewer (subagent).
- **Fix / lesson:** Spike numbers labelled "tuned-on", with the other screenshots held out for phase 5. Thresholds G1–G5 fixed before the first run, the `original` arm run twice, tokens recorded, labels frozen first.
- **Human verdict:** Confirmed

### #21 · Phase 1 (plan) · 2026-10-03
- **What the AI got wrong:** `compress()` used `convert("RGB")`, turning transparent pixels black, so dark text on a transparent PNG would be unreadable. The "no EXIF" test would also pass on an input with no EXIF.
- **Caught by:** AI, via the plan reviewer (subagent), who verified both with Pillow.
- **Fix / lesson:** Composite onto white first. Tests use a transparent PNG and EXIF orientation=6, so they can fail.
- **Human verdict:** Confirmed

### #22 · Phase 1 (plan) · 2026-10-03
- **What the AI got wrong:** Left key lookup to `genai.Client()`: the SDK prefers `GOOGLE_API_KEY` and falls back to the environment when `api_key` is empty, contradicting AC-12 ("only `GEMINI_API_KEY`"). No request timeout either, so a stalled call would hang (AC-1).
- **Caught by:** AI, via the plan reviewer (subagent), precedence confirmed in the SDK source.
- **Fix / lesson:** `tagger.py` reads `GEMINI_API_KEY` itself, fails clearly if empty, and passes it with `HttpOptions(timeout=...)`. The timeout is tuned in the spike.
- **Human verdict:** Confirmed

### #23 · Phase 1 · 2026-10-03
- **What the AI got wrong:** Two new tests had wrong expectations: one asserted G5 fails at 9 valid of 10 (exactly the 90% target, which passes), the other expected a title-only match though the fixture's summary also contained the word.
- **Caught by:** AI, when pytest failed at first run.
- **Fix / lesson:** Fixed the tests, not the code, which was right. Work out boundary arithmetic before writing the assertion.
- **Human verdict:** Confirmed

### #24 · Phase 1 · 2026-10-03
- **What the AI got wrong:** The harness never computed G4 (text-only query gate), though G4 was fixed in the approved plan before any run. Labels couldn't mark text-only queries, so `text_only_hits` read 0 whenever the model also tagged the word.
- **Caught by:** AI, via a fresh-context code reviewer (subagent), rated high.
- **Fix / lesson:** Labels gain an optional `text_queries` key, and the summary reports G4.
- **Human verdict:** Confirmed

### #25 · Phase 1 · 2026-10-03
- **What the AI got wrong:** The harness could report PASS for G1–G3 on the images that succeeded while other labelled calls failed or were rate-limited. It showed only group totals where swapped failures cancel out, and "Unstable cells" printed 0 without repeats, which looks like stability.
- **Caught by:** AI, via a code reviewer (subagent), who ran a case with 3 of 5 calls rate-limited.
- **Fix / lesson:** Gates say `INCOMPLETE` when any labelled call has no score. Added a per-image grid and a "Lost vs original" line. Instability is n/a without repeats and ignores rate limits.
- **Human verdict:** Confirmed

### #26 · Phase 1 · 2026-10-03
- **What the AI got wrong:** `compress()` turned a 16-bit greyscale PNG pure white with no error, so Gemini would get a blank image and return garbage tags.
- **Caught by:** AI, via a code reviewer (subagent), then reproduced.
- **Fix / lesson:** Scale 16-bit modes to 8-bit first, with a test that brightness survives.
- **Human verdict:** Confirmed

### #27 · Phase 1 · 2026-10-03
- **What the AI got wrong:** Tests were weaker than they looked: a mutation check found two deliberate bugs that passed everything, G2 using `any` instead of `all` (the test had one row) and `run()` never marking rows labelled (only hand-built rows were tested).
- **Caught by:** AI, in its own mutation check (one in-memory bug at a time), after the review.
- **Fix / lesson:** Added a two-row G2 test and a real-run test of the labelled flag. All 9 mutants are now caught.
- **Human verdict:** Confirmed

### #28 · Phase 1 · 2026-10-03
- **What the AI got wrong:** Smaller problems in the first harness and tagger: failed calls lost their token counts; query matching treated `ramen_shop` as one word and ignored accents, unlike FTS5; a comment asserted, unverified, that Gemini writes fields in schema order.
- **Caught by:** AI, via a code reviewer (subagent).
- **Fix / lesson:** `TaggingError` carries `usage`. The tokenizer splits on underscores and folds accents. The schema sends `propertyOrdering`, and comments say the order is requested and checked in the spike.
- **Human verdict:** Confirmed

### #29 · Phase 2 · 2026-10-03
- **What the AI got wrong:** `images` used `INTEGER PRIMARY KEY` without `AUTOINCREMENT`, so a deleted newest image's id was reused by the next upload, and a late tagging task for the deleted image could write its tags onto the new one.
- **Caught by:** AI, in its own test run: a test with a wrong assumption failed, and tracing why showed the id reuse.
- **Fix / lesson:** `AUTOINCREMENT`, plus tests that ids are never reused and a late result for a deleted image is discarded. Two tests fail with the old schema.
- **Human verdict:** Confirmed

### #30 · Phase 2 · 2026-10-03
- **What the AI got wrong:** The first backend retried every 429 after 5 s and 15 s, including a daily quota that says to retry in about 11 hours, so each image held a tagging slot for 20 s for nothing.
- **Caught by:** AI, in the live run against the real API, where all 7 uploads failed this way.
- **Fix / lesson:** `_suggested_wait` reads Google's retry hint, and only waits of 30 s or less count as transient. Tests cover short, long, missing and unreadable hints.
- **Human verdict:** Confirmed

### #31 · Phase 2 · 2026-10-03
- **What the AI got wrong:** A test expected an unreadable retry hint to mean "don't retry", contradicting the code's design (unreadable is as unknown as no hint).
- **Caught by:** AI, when pytest failed.
- **Fix / lesson:** Fixed the test, not the code. Decide the behaviour before writing the assertion.
- **Human verdict:** Confirmed

### #32 · Phase 2 · 2026-10-03
- **What the AI got wrong:** Told the human "gemini-3.1-flash-lite is also capped at 20 requests per day" and wrote it into the README. Wrong: the probe didn't pass `--model`, so it ran on the `.env` model (`gemini-3.5-flash`). Flash-lite had made about 50 calls that day without a limit.
- **Caught by:** AI, noticing 39 successful flash-lite calls contradicted a limit of 20, then re-running the probe with the model stated.
- **Fix / lesson:** Corrected the README, a code comment and the spike results, and re-ran the live check with the model explicit (all 7 tagged in 17 s). Pass the model explicitly in every probe, and check a surprising result against what you know.
- **Human verdict:** Confirmed

### #33 · Phase 2–3 · 2026-10-03
- **What the AI got wrong:** Robustness gaps in the first backend and UI: tagging shared the request thread pool and could starve the API; a failed database write left an image pending forever; a huge id caused a 500; AC-1's 60 s wasn't bounded; another site could POST uploads and spend the quota; and in the UI a slow old search could overwrite a newer one, timers stacked, the grid rebuilt every 2 s (losing focus and thumbnails), and polling stopped after one failed request.
- **Caught by:** AI, via a fresh-context reviewer (subagent) on the finished backend and UI.
- **Fix / lesson:** A dedicated 3-thread pool, guarded outcome recording, bounded ids, a 50 s retry deadline, an Origin check, a request counter, change detection and a retry timer, each with a test or browser check. A mutation check then found two new tests passing by accident, and those were fixed.
- **Human verdict:** Confirmed

### #34 · Docs cleanup · 2026-10-03
- **What the AI got wrong:** Asked which docs were problematic, suggested "rewrite or remove" the two phase plans. It did not say that the brief requires agent plans in `planning/` (see #15), or that the plans hold the verified facts and decisions behind #12 to #22.
- **Caught by:** Human, who asked why deletion was suggested.
- **Fix / lesson:** Rewrote both in a neutral voice and kept all their content. Before proposing to delete a file, check whether a requirement or another doc depends on it.
- **Human verdict:** Confirmed

### #35 · Docs cleanup · 2026-10-03
- **What the AI got wrong:** Offered to change the "voice" of the 33 corrections. That would have altered text the human had confirmed, and goes against §7 ("don't tidy the story").
- **Caught by:** AI, on re-reading §7 before editing.
- **Fix / lesson:** Asked the human first. The human chose a layout change, then condensing. The entries were condensed with numbers, dates, phases, who caught each mistake and the verdicts unchanged, a note added at the top, and the long form linked.
- **Human verdict:** Confirmed

### #36 · Docs cleanup · 2026-10-03
- **What the AI got wrong:** Estimated that `design.md` would shrink to about 125 lines. The rewrite came out at 231, longer than the original 223. The first condensed corrections were also only 5% shorter, not the concise version asked for.
- **Caught by:** AI, by counting lines and words after each rewrite.
- **Fix / lesson:** Reported the real numbers to the human. `design.md` stayed because it now separates what was built from what was deferred. The corrections were tightened again and ended 16% shorter. Measure before claiming a size.
- **Human verdict:** Confirmed

### #37 · Docs cleanup · 2026-10-03
- **What the AI got wrong:** Trimming `design.md` section 4 removed the five-category list that the phase 1 plan cites by section number.
- **Caught by:** AI, while checking which files cite `design.md` sections.
- **Fix / lesson:** Restored the list in the chips note. Search for citations before cutting a section.
- **Human verdict:** Confirmed

### #38 · Docs cleanup · 2026-10-04
- **What the AI got wrong:** Did not log #34 to #37 when they happened, as §7 requires. They were added at the final check.
- **Caught by:** AI, at the final check against the repo's own rules.
- **Fix / lesson:** Logged all four together. Log each correction when it happens.
- **Human verdict:** Confirmed

### #39 · Demo prep · 2026-10-04
- **What the AI got wrong:** Assumed the demo would be live and wrote the preparation for it (stage a failure in front of an audience, keep live uploads to 3, keep a fallback screenshot), although handoff 04 already listed "the demo recording" as still to do.
- **Caught by:** Human, who said the demo is a recording.
- **Fix / lesson:** Redid the advice for a recorded demo, where retakes and cuts are possible. Re-read the handoff and ask how the demo is delivered before planning around it.
- **Human verdict:** Confirmed

### #40 · Post-build · 2026-10-04
- **What the AI got wrong:** Retry tagging is offered on healthy cards and clears the tags and search entry before calling Gemini, so a failed retry leaves a good image failed and unsearchable. The same image also gets different tags on a retry (temperature left at the default, and the spike never repeated a run), which nobody measured or flagged.
- **Caught by:** Human, who clicked Retry tagging on a Mount Fuji post and saw the title, summary and two tags change. The AI then confirmed the lost tags with a scratch script and no Gemini call.
- **Fix / lesson:** Retry now exists only for failed images: the button is hidden otherwise, the API refuses a tagged image with 409, and the database reset works only from failed. Two new tests fail under the old behaviour. The run-to-run variation is still unmeasured. Don't clear good data before the replacement exists.
- **Human verdict:** Confirmed

### #41 · Post-build · 2026-10-04
- **What the AI got wrong:** Told the human that offering Retry only on failed cards "is what the original plan describes". Only F6 says that. Plan §7 ("Retag: overwrites AI fields") and `design.md` (Retry among the detail actions) describe retry on any card, so the human approved a departure from the plan on a wrong description.
- **Caught by:** AI, when reading the plan and design again before editing the code.
- **Fix / lesson:** Told the human before building. The code follows the human's approval; the plan and design notes are proposed, not edited. Check the plan text before saying what it says.
- **Human verdict:** Confirmed
