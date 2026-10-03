# Handoff 05: Retry only on failed images
Date: 2026-10-04
Goal: Fix a bug the owner found: Retry tagging on a tagged image gave different tags, and could wipe a good result.

Done:
- Found two causes. Gemini's output varies between runs (temperature is at the model default and the spike never repeated a run). And Retry on a tagged image cleared its tags and search entry before the new call, so a failed retry left a good image failed and unsearchable. The second was reproduced with a fake tagger and no Gemini call.
- Retry now exists only for failed images. `db.reset_pending` moves only failed rows to pending, `POST /api/images/{id}/retag` answers 409 for a tagged image, and the detail dialog shows the button only on failed cards. Commit `33d566c`.
- Replaced 2 tests that described retagging a tagged image and added 2 that fail under the old behaviour. 292 tests pass.
- Logged #40 and #41 in `corrections.md`, confirmed by the owner (`1abb75e`). Added "as built" notes to `01-full-plan.md` §7 and §11 and to `design.md` §5.

Decisions (and why):
- Failed-only retry, not "keep the old tags until the new result arrives". Less code, and a pending image keeps the rule that it has no tags. This departs from plan §7 and design §5, which allowed retag on any card, and the notes say so.
- Temperature left alone. Lowering it would change a prompt tuned at the default, so Google's docs for the model (hard rule 10) and a G1 to G5 re-run come first.

Not done / blockers:
- The run-to-run variation is unmeasured: `python -m eval.run_eval --images eval/synthetic --labels eval/synthetic/labels.json --sizes 1600 --repeats 5` (about 35 real calls, needs the owner's OK).
- A tagged image can no longer be re-tagged at all. This is deliberate.
- `02-mvp-outcome.md` is unchanged. "Detail with retry and delete" is still true for failed images.

Next step: measure the variation, then decide whether to change temperature or accept it and say so in the README.

Files touched: `app/db.py`, `app/main.py`, `app/static/index.html`, `tests/test_db.py`, `tests/test_api.py`, `planning/corrections.md`, `planning/project_plan/01-full-plan.md`, `planning/design/design.md`, this file.

How to verify: `.venv\Scripts\python.exe -m pytest -W error` (292 passed). In the app, a tagged card has no Retry tagging button and a failed card does.
