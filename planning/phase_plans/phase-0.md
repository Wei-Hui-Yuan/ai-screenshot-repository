# Plan: Phase 0, repo skeleton

> **Status: record.** The plan as approved on 2026-10-03, before phase 0 was built. The wording was tidied afterwards (neutral voice, file names updated to the renamed plan); the content is unchanged. `projectplan.md` is now [`01-full-plan.md`](../project_plan/01-full-plan.md), with the same section numbers. What was built is in [handoff 02](../handoffs/02-phase-0-skeleton.md).

## Context
Phase 0 of `01-full-plan.md` §9 (handoff 01, "Next step"). The planning docs are done. What's left: `git init`, a runnable skeleton, `.gitignore`, `.env.example`, `requirements.txt`, and commits.

No AC is completed in phase 0. It lays groundwork for **AC-11** (pytest runs with no API key) and **AC-12** (a fresh clone installs and needs only `GEMINI_API_KEY`), and puts **hard rule 1** in place for `.env` and `data/`.

Environment, checked read-only:
- Python 3.12.8 is the only interpreter.
- git 2.54, `init.defaultBranch=master`, autocrlf on, name and email set.
- PowerShell policy is RemoteSigned, so `Activate.ps1` runs.
- **Global Python already has fastapi 0.139.2, uvicorn 0.51.0, watchfiles and pytest.** So every check runs through `.venv\Scripts\python.exe -m ...`, never a bare `pip`, `pytest` or `uvicorn`.

## Decisions by the owner
- **Screenshots:** no new ignore rules yet. Decide in phase 1. Staging by name is the guard until then.
- **Assessment PDF:** kept out of git with `.git/info/exclude`, a local-only ignore that the public `.gitignore` won't mention.
- **Skeleton:** the runnable minimum. `db.py`, `images.py`, `search.py` (phase 2), `tagger.py`, `schemas.py`, `eval/` (phase 1), and `run_eval.py` and `README.md` (phase 5) are created by the phase that writes their code.

## Files

| File | Contents |
|---|---|
| `.gitignore` | `.env`, `.env.*`, `!.env.example`. `data/`. `*.db`, `*.db-*`, `*.sqlite*` as a safety net, since a stray DB holds screenshot text. `.venv/`, `__pycache__/`, `.pytest_cache/`. `.claude/settings.local.json`. |
| `.env.example` | `GEMINI_API_KEY=` and `GEMINI_MODEL=`, both blank. The model is chosen in the phase 1 spike (rule 10). Short comments, including the free-tier privacy note. |
| `requirements.txt` | Exact pins, listed below. |
| `pytest.ini` | `testpaths = tests`, `pythonpath = .`, so the plain `pytest` command in §2 can import `app`. |
| `app/__init__.py` | Empty. |
| `app/main.py` | `app = FastAPI(...)` and `GET /` returning `FileResponse(Path(__file__).parent / "static" / "index.html")`. The route is already in the plan (§5, §7). Nothing else. |
| `app/static/index.html` | Placeholder page with the app name. Phase 3 replaces it. |
| `tests/test_main.py` | `GET /` returns 200 HTML containing the app name. |
| `.claude/launch.json` | Preview config running the §2 uvicorn command through the venv's Python. Whether to commit it is the owner's call. |
| `planning/phase_plans/phase-0.md` | This plan, saved in the repo. Agent plans are kept in `planning/`, not only in plan mode's own location (correction #15). |
| `planning/agents/agents.md` §2 | Run command becomes `uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000`. Without watchfiles, uvicorn's reloader scans the whole working directory, `.venv` included, every 0.25 s (from the 0.54.0 source). |

### requirements.txt
```
fastapi==0.142.2
starlette==1.7.0           # FastAPI no longer caps it; pinned so fresh installs match
uvicorn==0.54.0
python-multipart==0.0.32   # FastAPI needs it to read file uploads (phase 2)
pillow==12.3.0
google-genai==2.28.0
pydantic==2.13.5           # imported directly for the tag schema (phase 1)
python-dotenv==1.2.4       # loads .env for the app and the eval script

pytest==9.1.1
httpx2==2.13.1             # Starlette's TestClient uses it (falls back to httpx with a warning)
```
- **Dependencies not named in `01-full-plan.md` §4, which need the owner's OK:** `python-multipart`, `python-dotenv`, `httpx2`, plus the `starlette` pin.
- `httpx2` is Pydantic's continuation of httpx. Starlette 1.7.0 lists it in its own extras. google-genai still pulls in plain `httpx`. The pins don't conflict (checked `requires_dist`).
- google-genai is at major version 2. Phase 1 must read the current docs, not 1.x examples.

## Steps
1. Run `git init` (branch `master`, per the git config) and add the PDF to `.git/info/exclude`.
2. **Propose commit 1** and wait for the owner's OK. It holds the 8 planning files exactly as approved in session 1: `CLAUDE.md`, `AGENTS.md`, `planning/project_plan/projectplan.md`, `planning/agents/agents.md`, `planning/claude/claude.md`, `planning/design/design.md`, `planning/corrections.md`, `planning/handoffs/01-planning.md`.
3. Log corrections #12–#15 (below) as Pending and ask the owner for verdicts.
4. Write the files above. Verify. Fix the code if anything fails.
5. Fresh-context subagent review. Report its findings to the owner as-is.
6. **Propose commit 2:** the skeleton, the `agents.md` §2 edit and the saved plan, listed by name. After it lands, do a fresh-clone check.
7. Write `planning/handoffs/02-phase-0-skeleton.md`. **Propose commit 3:** the handoff and `corrections.md`.

## Corrections to log (found by the fresh-context plan review)
- #12: The draft said `httpx` is what FastAPI's TestClient needs. Starlette 1.7.0 now prefers `httpx2`.
- #13: The draft's ignore check used `git check-ignore -v`. That also reports `!` matches and exits 0, so `.env.example` would have looked ignored.
- #14: The draft's checks didn't account for the packages already installed in global Python. A bare `pytest` or `uvicorn` could have passed the clean-install check falsely and hidden the reloader issue.
- #15: The draft left the plan only in `~/.claude/plans`. The assessment brief requires agent-generated plans in `planning/`.

## Verification
- `git check-ignore -v .env .env.local data/app.db x.db`: each matches a non-`!` rule. `git check-ignore .env.example app/main.py` (no `-v`): no output, exit 1. `git check-ignore -v` on the PDF matches `info/exclude`.
- `python -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `pip check`.
- In one shell: `.venv\Scripts\Activate.ps1`, confirm `pytest` resolves to `.venv`, run `pytest` with `GEMINI_API_KEY` unset. Expect 1 passed, 0 warnings.
- Start the server with the preview. Expect the log to show `StatReload`, the watched dir `app`, and `http://127.0.0.1:8000` (rule 7). `GET /` should return the page.
- Before commit 2: `git ls-files --others --exclude-standard` lists exactly the intended files.
- After commit 2: clone into the scratchpad, then install and run `pytest` there.
- Not verifiable in phase 0: `python -m eval.run_eval` (phase 5), and anything that needs the key.
