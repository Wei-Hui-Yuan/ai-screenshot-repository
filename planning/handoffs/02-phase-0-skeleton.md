# Handoff 02: Phase 0 skeleton
Date: 2026-10-03
Goal: Finish phase 0 (projectplan §9): git repo, runnable skeleton, `.gitignore`, `.env.example`, `requirements.txt`.

Done:
- `git init` (branch `master`) and 3 commits: `a02c83d` planning docs, `3d9db04` skeleton, `32e3ca1` preview config.
- Skeleton: `app/main.py` serves a placeholder page at `/`, one smoke test, `pytest.ini`, pinned `requirements.txt`.
- Verified: fresh clone, install, `pip check` clean, `pytest` 1 passed with `-W error` and no key; server on `127.0.0.1:8000` watching `app/` only.
- Fresh-context subagent reviewed the plan and the finished work. Corrections #12–#16 logged, all Confirmed.

Decisions (and why):
- Pins on top-level packages only; their dependencies can drift on a fresh install. Fine for v1.
- Added `python-multipart`, `python-dotenv`, `httpx2` and a `starlette` pin (not in projectplan §4). Approved with the plan.
- `agents.md` §2 run command gains `--reload-dir app`, so the reloader skips `.venv`.
- The assessment PDF is kept out of git via `.git/info/exclude`. FastAPI `/docs` left on for now.
- No ignore rule for screenshots yet. Staging by name is the only guard.

Not done / blockers:
- Decide how to keep personal screenshots out of git before any go in `eval/images/`.
- `GEMINI_API_KEY` and 15–20 English screenshots (about 5 for phase 1) still needed.
- Open: flagged images, stage-and-confirm, model choice (`projectplan.md` §11). Session log not exported yet.

Next step: **Phase 1, tagging spike.** Read the current `google-genai` 2.x docs first (the global Python has 1.x). Run the schema on about 5 screenshots at original, 1600 px and 1024 px, then lock prompt v1, the compression setting and the model.

Files touched: `.gitignore`, `.env.example`, `requirements.txt`, `pytest.ini`, `app/__init__.py`, `app/main.py`, `app/static/index.html`, `tests/test_main.py`, `.claude/launch.json`, `planning/agents/agents.md`, `planning/phase_plans/phase-0.md`, `planning/corrections.md`, this file.

How to verify: always use the venv, not global Python. `python -m venv .venv`, `.venv\Scripts\python.exe -m pip install -r requirements.txt`, then `.venv\Scripts\python.exe -m pytest` (1 passed).
