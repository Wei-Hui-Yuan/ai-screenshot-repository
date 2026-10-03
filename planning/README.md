# planning/: where to start

Written on 2026-10-03, apart from the final check on 2026-10-04.

## The short version
- **What it is.** A local web app: drop in screenshots, Gemini tags each one, and a search word finds them. v1 also answers one question: how well does Gemini tag real screenshots? ([spike-results.md](spike-results.md))
- **AI tools.** Claude Code was the main coding agent. It drafted the plans, wrote the code and tests, and ran the checks. The owner chose the problem, set the scope, wrote the eval labels, and approved every plan, commit and correction. Gemini is the model inside the app, not a development tool.
- **Where the AI helped.** Reviewer subagents, which read the work without seeing the author's reasoning, caught 22 of the 33 mistakes logged during the build. A live run against the real API caught the quota problem (#30).
- **Where it failed.** Facts taken from memory or from a summary (#12, #19, #32), tests with wrong expectations (#23, #31), and gaps in the first designs (#6, #9, #10). All are in [corrections.md](corrections.md), with how each was caught and fixed.
- **What was deferred.** Category and place chips, "Load more", a separate detail page, toasts and per-card polling. They were postponed for time and to keep v1 a proof of concept. See [02-mvp-outcome.md](project_plan/02-mvp-outcome.md).
- **Weakest part.** The evidence on tag quality is thin: the prompt was tuned and judged on the same 7 synthetic and 5 real images, and the hold-out evaluation was not run. The place-recall criterion (AC-3) stays provisional.
- **Next.** Run the hold-out evaluation on 15 to 20 real screenshots, build the deferred UI features, make tagging aware of free-tier quotas (or move to a paid tier), then manual tag editing. ([01-full-plan.md](project_plan/01-full-plan.md) §10)

## Reading order

| # | Document | Status | What it tells you |
|---|---|---|---|
| 1 | [project_plan/01-full-plan.md](project_plan/01-full-plan.md) | Baseline, annotated | The original plan: every phase and feature we wanted, each tagged BUILT, CHANGED, DEFERRED or LATER |
| 2 | [project_plan/02-mvp-outcome.md](project_plan/02-mvp-outcome.md) | Record | What phases 2 to 5 actually built, where the build departed from the plan, and the evidence for all 14 acceptance criteria |
| 3 | [spike-results.md](spike-results.md) | Record | How well Gemini tags screenshots, and the locked prompt, model and compression |
| 4 | [corrections.md](corrections.md) | Log, complete | Every mistake the AI made or caught, and the human's verdict on each. Condensed, with the long form linked |
| 5 | [design/design.md](design/design.md) | Spec, annotated | The UI design, with a "Designed but not built" note for each feature deferred to a later version |
| 6 | [phase_plans/](phase_plans/) | Records | The plans for phases 0 and 1 as approved, with amendments |
| 7 | [handoffs/](handoffs/) | Records, oldest first | What each working session finished and what came next |
| 8 | [agents/agents.md](agents/agents.md), [claude/claude.md](claude/claude.md) | Living rules | The rules the coding agent follows, and its checklist |

**Status words.** *Annotated* means the original text is kept and notes were added about what was built or deferred. *Record* means it describes what happened, so its content is not changed afterwards. Wording may be tidied and notes added, and each file says so at the top. *Living* means it is kept up to date.

**What was deferred, and why:** some planned UI features were postponed to a later version, for time and to keep v1 a proof of concept. They are listed in [02-mvp-outcome.md](project_plan/02-mvp-outcome.md), and their designs are kept in [design.md](design/design.md).

**Renamed files**
- `projectplan.md` is now `project_plan/01-full-plan.md`. Section numbers are unchanged, so older references to "projectplan.md section N" point there.
- The combined phases 2 to 5 plan, `phase_plans/mvp.md`, was rewritten as `project_plan/02-mvp-outcome.md`. The version approved before building is kept in Git: [mvp.md at commit `e871b50`](https://github.com/Wei-Hui-Yuan/ai-screenshot-repository/blob/e871b50b63616c245c2ad897c8fd54d3951e0515/planning/phase_plans/mvp.md).

The code, how to run it and its trade-offs are in the [root README](../README.md).
