# CLAUDE.md: working checklist

Claude Code checklist for this repo. The rules live in `planning/agents/agents.md`, which is loaded alongside this file. The § numbers point there.

## Start of session
- [ ] Read the latest file in `planning/handoffs/` and the plan sections for today's task (§1).
- [ ] Restate the goal and which acceptance criteria (AC-IDs) it covers.
- [ ] 3 or more files, or about 20 minutes or more? Use plan mode: write the plan, wait for approval, then build (§5).
- [ ] For multi-step work, keep a task list so progress is visible.

## While building
- [ ] One concern at a time, with tests alongside. Run `pytest` after each change (§2, §5).
- [ ] Before writing Gemini code, fetch the current `google-genai` docs. Don't write model names or parameters from memory (§4.10).
- [ ] Check each change against the hard rules (§4), especially: nothing from `.env` or `data/` in git, parameterised SQL, Gemini output validated by Pydantic, `127.0.0.1` only.
- [ ] Unclear plan or out-of-scope idea? Stop and ask (§5).

## When corrected, or when you catch your own mistake
- [ ] Append a row to `planning/corrections.md` with the verdict `Pending`, then ask the human for their verdict (§7).

## Before saying "done"
- [ ] Run `pytest` and show the result. Name anything you didn't verify (§5).
- [ ] At the end of each phase, get a fresh-context review from a subagent or `/code-review` that hasn't seen your reasoning. Report its findings to the human. Don't fix or dismiss them silently.
- [ ] Propose a commit: the exact files and the message. Commit only after the human approves (§5).

## End of session
- [ ] Write `planning/handoffs/NN-short-title.md` using the template (§6).
- [ ] If commands changed, update `agents.md` §2.
