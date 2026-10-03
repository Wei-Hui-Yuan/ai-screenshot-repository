# planning/: where to start

Everything here was written during one working day, 2026-10-03. Read in this order.

| # | Document | Status | What it tells you |
|---|---|---|---|
| 1 | [project_plan/01-full-plan.md](project_plan/01-full-plan.md) | Frozen baseline | The original plan: every phase and feature we wanted, each tagged BUILT, CHANGED, CUT or LATER |
| 2 | [project_plan/02-mvp-outcome.md](project_plan/02-mvp-outcome.md) | Record | What phases 2 to 5 actually built, where the build departed from the plan, and the evidence for all 14 acceptance criteria |
| 3 | [spike-results.md](spike-results.md) | Record | How well Gemini tags screenshots, and the locked prompt, model and compression |
| 4 | [corrections.md](corrections.md) | Log, complete | Every mistake the AI made or caught, and the human's verdict on each |
| 5 | [design/design.md](design/design.md) | Frozen spec | The UI design. A banner at the top lists the parts that were superseded |
| 6 | [phase_plans/](phase_plans/) | Records | The plans for phases 0 and 1 as approved, with amendments |
| 7 | [handoffs/](handoffs/) | Records, oldest first | What each working session finished and what came next |
| 8 | [agents/agents.md](agents/agents.md), [claude/claude.md](claude/claude.md) | Living rules | The rules the coding agent follows, and its checklist |

**Status words.** *Frozen* means the wording is left as written. *Record* means it describes what happened and is not edited afterwards. *Living* means it is kept up to date.

**Two things that moved**
- `projectplan.md` is now `project_plan/01-full-plan.md`. Section numbers are unchanged, so older references to "projectplan.md section N" point there.
- The combined phases 2 to 5 plan, `phase_plans/mvp.md`, was rewritten as `project_plan/02-mvp-outcome.md`. The version approved before building is kept in Git: [mvp.md at commit `e871b50`](https://github.com/Wei-Hui-Yuan/ai-screenshot-repository/blob/e871b50b63616c245c2ad897c8fd54d3951e0515/planning/phase_plans/mvp.md).

The code, how to run it and its trade-offs are in the [root README](../README.md).
