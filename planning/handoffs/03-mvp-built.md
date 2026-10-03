# Handoff 03: Spike locked, backend and UI built
Date: 2026-10-03
Goal: Finish the phase 1 spike, cut scope for speed, and build the MVP (phases 2–5 merged, see `planning/phase_plans/mvp.md`).

Done:
- Spike locked (`planning/spike-results.md`): prompt `v1`, `gemini-3.1-flash-lite`, 1600 px WebP q80, 45 s timeout. Synthetic set passes G1–G5.
- Backend: `db.py`, `search.py`, `images.py` (check, hash, store), `main.py` (routes, tagging pool, Origin check), `tagger.py` (`transient`, retry hint). One-page UI with a detail dialog.
- 278 tests pass with Gemini mocked. Live run with real Gemini: 7 synthetic uploads tagged in 17 s, and search, flag, dedupe, rejection and hostile text all behaved.
- A fresh-context review led to fixes. Corrections #29–#33 are logged (Pending).

Decisions (and why):
- Demo and eval data is the fake set from `eval/make_synthetic.py` (public-safe). The real photos stay local.
- Cut for speed: chips and facets, a separate detail page, load more, toasts, per-card polling, hold-out evaluation. The README says so.
- README states the limits: free-tier quotas, 503s, English only, local only, "legacy" `generate_content`.

Not done / blockers:
- **Your `.env` still says `GEMINI_MODEL=gemini-3.5-flash`** (20 requests per day). Change it to `gemini-3.1-flash-lite` or the app will hit the quota.
- Session log export (the brief asks for it) and the demo recording.
- Not tested: a re-upload racing a delete, real load, the Windows locked-file delete in practice.
- Proposed, not made: update `agents.md` §3 (add `search.py`, `eval/make_synthetic.py`, `tests/helpers.py`, the `DATA_DIR` setting).

Next step: after the commits, run the fresh-clone check, export the session, record the demo by dragging the `eval/synthetic/` images in, and make the final commit.

Files touched: `app/{db,search,images,main,tagger}.py`, `app/static/index.html`, `tests/*`, `README.md`, `planning/{corrections.md,spike-results.md,design/design.md,project_plan/projectplan.md}`, this file.

How to verify: `.venv\Scripts\python.exe -m pytest -W error` (278 passed). Then run the app (see `README.md`), generate `eval/synthetic/` with `python -m eval.make_synthetic`, drag the images in, and search `kyoto`, `48213`.
