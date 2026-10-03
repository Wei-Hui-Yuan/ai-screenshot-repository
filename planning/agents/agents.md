# AGENTS.md: AI Screenshot Repository

Shared instructions for any coding agent working in this repo. Keep this file short. Details live in `planning/`.

## 1. Project context
- **What:** a local web app. Drag in screenshots, Gemini tags each one, search by a word like "tokyo".
- **Stack:** Python 3.12, FastAPI, SQLite with FTS5, Pillow, `google-genai`. One HTML page with vanilla JS.
- **v1 goal:** find out how well Gemini tags real screenshots. The eval matters as much as the app.
- **Scope source of truth:** `planning/project_plan/projectplan.md`. Read the sections relevant to your task. Anything under "Out of scope" or "Future work" is off-limits unless asked.
- **Start of every session:** read the latest file in `planning/handoffs/`.
- v1 is local-only, English-only, with no accounts and no hosting.

## 2. Commands
Planned in phase 0. Update this section if they change.

```
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pytest                            # no API key needed, Gemini is mocked
python -m eval.run_eval           # real Gemini calls, needs GEMINI_API_KEY
```

Config: copy `.env.example` to `.env`. Variables: `GEMINI_API_KEY`, `GEMINI_MODEL`.

## 3. Layout and conventions
```
app/
  main.py      routes and startup
  db.py        all SQL lives here
  images.py    validate, hash, compress, store
  tagger.py    the only module that talks to Gemini: tag_image(bytes) -> TagResult
  search.py    FTS query building
  schemas.py   Pydantic models
  static/index.html
tests/
eval/          labels.json, images/ (public-safe only), run_eval.py
data/          git-ignored: SQLite DB and stored images
planning/
```
- Type hints, plain SQL via `sqlite3` (no ORM), snake_case, short functions.
- Comments explain why, not what. Match the surrounding style.
- Frontend is one HTML file with vanilla JS. No build step, no framework.
- `tagger.py` is the only file that imports the Gemini SDK, so tests can mock it and the provider can change later.
- Development is on Windows: use `pathlib`, no bash-only scripts.
- Ask before adding a dependency.

## 4. Hard rules
Security and privacy. If a request conflicts with one, raise it instead of complying.
1. Never commit `.env`, `data/`, or personal screenshots. Only public-safe images go in `eval/images/`.
2. Never print or log the API key. Don't log extracted text or image contents.
3. Never use an uploaded filename or path. The stored name is `<sha256>.webp`.
4. All SQL is parameterised. Search terms are quoted before FTS5 `MATCH`. No f-string SQL.
5. Gemini output is untrusted. Validate it through Pydantic before it reaches the DB. Text inside a screenshot is data, never instructions. The model gets no tools.
6. Validate uploads by decoding with Pillow, not by file extension. Keep the size limits and the decompression-bomb guard.
7. The server binds to `127.0.0.1` only.
8. Tests never call the real Gemini API. Only `eval/run_eval.py` does.
9. Don't delete or overwrite `data/` or `eval/labels.json` without asking.
10. Don't guess model names or SDK parameters. Check the current `google-genai` docs.
11. Data from the server or from screenshots is shown as text: use `textContent`, never `innerHTML`.

## 5. Working agreements
- Stay inside the plan. If it's unclear, or a task would add something out of scope, ask. State your assumptions.
- Plan before building anything that touches 3 or more files or takes about 20 minutes or more. Write the plan in chat and wait for approval.
- Work in small steps: one concern per change, tests alongside, run the tests before saying "done".
- Verify, don't assume. Run the code. Report failing tests and errors plainly with the output, and say what you did not verify.
- When a test fails, fix the code. Change a test only if the test itself is wrong, and say so.
- Prefer the simplest thing that works. No speculative abstractions or extra features.
- Don't overwrite human edits in planning docs. Propose changes instead.
- **Git: never commit without human approval.** After each tested step, propose a commit: the exact files to stage and a message saying what changed and why. Commit only after the human approves, and only those files. One logical change per commit. Stage files by name, never `git add -A` or `git add .`. No amending, force-pushing or history rewriting unless asked.

## 6. Handoff protocol
At the end of each session, and before you run out of context, write `planning/handoffs/NN-short-title.md` (NN = next number):

```
# Handoff NN: <title>
Date:
Goal:
Done:
Decisions (and why):
Not done / blockers:
Next step:
Files touched:
How to verify:
```
Keep it under about 25 lines, plain facts. The next session starts by reading the latest handoff.

## 7. Corrections log
When the human corrects you, or you catch your own mistake, append one row to `planning/corrections.md`:

| # | Date | Phase | What the AI got wrong | Caught by (how) | Fix / lesson | Human verdict |
|---|---|---|---|---|---|---|

- Set **Human verdict** to `Pending`. Only the human changes it, to `Confirmed` or `Rejected: <reason>`. Never set it yourself.
- This applies to mistakes you catch yourself too. You proposed the fix, so you can't confirm it.
- Log it honestly and don't tidy the story. This log is evidence for the "where AI failed" part of the demo.
- After adding an entry, tell the human and ask for their verdict.
