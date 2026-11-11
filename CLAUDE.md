@AGENTS.md

## Claude Code specifics

- **Your role is builder.** The planning chat (claude.ai Project "AIC390") writes self-contained specs into
  `docs/handoffs/`. Run `/handoff <id>` to implement one and fill its Result section. Never edit a handoff's
  Request section; if it is wrong or impossible, write why under Result → Open questions and stop.
- At session start, read `docs/STATUS.md`. When a task ends, update it (a few lines, not a diary).
- Use plan mode for work touching more than two files or starting a new layer; skip it for one-line fixes.
- **Show evidence, don't assert.** Before saying something works: run `pytest -q` and `ruff check .`; for an
  experiment, show the command you ran and the numbers from its `summary.json`.
- Before calling a deliverable done, have the `reviewer` subagent check the diff against that deliverable's
  criteria in `docs/course/requirements.md`. Fix only findings that affect correctness or the requirements.
- Keep broad reading (lecture notes, many files) in subagents so the main context stays on the task.
- When compacting, preserve: the active handoff id, modified files, commands run, and every measured number.
- Workflows: `/handoff`, `/experiment`, `/weekly-report`. Subagents: `reviewer`, `red-teamer`.
- Never `git push`, `git tag` or force anything unless the user asks in this session. Tags `week-N` are created
  only when the user says the week is final.
