---
name: handoff
description: Implement a work request written by the planning chat in docs/handoffs/, then record the result in the same file.
argument-hint: "[handoff id or path, e.g. 003]"
disable-model-invocation: true
---

Implement handoff `$ARGUMENTS` from `docs/handoffs/` (match the id prefix if only a number is given).

1. Read the handoff file, `docs/STATUS.md`, and the deliverable IDs it names in `docs/course/requirements.md`.
2. If the Request is ambiguous, contradicts the repo or a course rule, or needs paid API calls beyond its stated
   budget, stop: write the problem under **Result → Open questions**, set `status: blocked`, and tell the user.
3. Set `status: in-progress`. Plan first if it touches more than two files.
4. Implement. Meet every acceptance criterion literally; run the exact verification commands listed.
5. Use the `reviewer` subagent on the diff against the acceptance criteria. Fix findings that affect correctness
   or the criteria; list the rest as optional.
6. Fill **Result**: what changed (files), commands run with their real output summary, every measured number with
   n / CI / script path, deviations from the Request and why, open questions.
7. Set `status: done`, update `docs/STATUS.md`, and commit with the right area prefix
   (`[data]`, `[agent]`, `[eval]`, `[docs]`, `[infra]`) and the handoff id in the message. Do not push.

Never edit the Request section. Never report a number you did not just measure.
