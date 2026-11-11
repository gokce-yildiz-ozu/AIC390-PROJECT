# How we use AI tools on this project

AI tools are allowed and expected in this course (R15), but every line is ours to explain, and every use is
disclosed in section 9 of the weekly report. This page sets up two Claude surfaces so they work as one team.

## The two surfaces

| | claude.ai Project "AIC390" (planner / reviewer) | Claude Code in VS Code (builder) |
|---|---|---|
| Sees | Handbook, syllabus, Module 1–4 PDFs, lecture decks, our chats; the repo when synced or cloned | This repo and your machine; **not** the course PDFs or the claude.ai chats |
| Good at | Deciding what to build and measure, experiment design, reading reports/slides against the rubric, Q&A prep, explaining concepts | Writing and running code, producing numbers, tests, commits |
| Writes | `docs/handoffs/NNN-*.md` (Request), reviews | Code, `results/`, handoff Result, `docs/STATUS.md` |
| Instructions | `docs/claude-project-instructions.md` (paste into the Project) | `CLAUDE.md` → `AGENTS.md`, `.claude/` |

## The loop

```
 claude.ai Project                      repo (GitHub)                       Claude Code (VS Code)
 plan week N  ──writes──▶  docs/handoffs/NNN.md (Request)  ──/handoff NNN──▶  implement, run, measure
                                                                                  │ reviewer subagent
 review vs rubric ◀──reads── handoff Result + results/ + STATUS.md ◀──commits────┘
   │ accepted → next handoff;  gaps → follow-up handoff
   └─ weekly: /weekly-report N in Claude Code → paste draft here for a rubric pass → tag week-N
```

1. **Plan** in the claude.ai Project: which deliverables this week, what to measure, what "done" means.
   The output is a handoff file following `docs/handoffs/TEMPLATE.md`, self-contained, with acceptance criteria
   that a command can check.
2. **Get it into the repo.** If the planning chat can push, it commits the handoff. Otherwise download the file
   and commit it (`[docs] handoff NNN`).
3. **Build** in VS Code: `git pull`, then `/handoff NNN`. Claude Code implements, runs the checks, has the
   `reviewer` subagent check the diff, fills the Result, updates `STATUS.md`, commits. You push.
4. **Review** in the claude.ai Project: sync the repo (or let it clone), ask for a review of handoff NNN.
5. **Report**: `/weekly-report N` drafts and checks the report; the planning chat does a final rubric read.

## Habits that make Claude Code much better

- **One task per session.** `/clear` between unrelated tasks; after two failed corrections, `/clear` and
  re-prompt with what you learned. A long, messy session performs worse than a fresh one.
- **Plan mode** (`Shift+Tab` until "plan mode on") for anything multi-file or new; skip it for small fixes.
- **Give it a check it can run**: a test, `--dry-run`, an expected output. "Run X and iterate until it passes"
  beats "implement X". Ask for the command output as evidence.
- **Point at files** with `@path` instead of describing them; paste errors verbatim.
- **Fresh eyes for review**: the `reviewer` subagent, or a second session, reviews what the first one wrote.
- **Rewind instead of arguing**: `Esc` stops it, `Esc Esc` or `/rewind` restores an earlier checkpoint (only
  file edits made by Claude are tracked; git is still the real safety net).
- **Side questions** that shouldn't pollute the task context: `/btw`.
- **Check what loaded**: `/context` shows whether `CLAUDE.md`/`AGENTS.md` were read.
- Name long-lived sessions with `/rename` and resume with `claude --continue` / `--resume`.

## Setup per member (Windows)

1. Install Git, Python 3.12, VS Code, and the Claude Code extension; sign in.
2. Clone the repo, open the folder in VS Code, follow the commands in `AGENTS.md`.
3. Put API keys only in `.env`. Claude Code is configured to refuse reading it.
4. Personal, uncommitted preferences go in `CLAUDE.local.md` (gitignored).
5. Each member who uses a claude.ai Project pastes `docs/claude-project-instructions.md` into the Project's
   instructions and adds this repo to the Project knowledge via GitHub (press **Sync now** after pushes).

## Rules that apply to AI output too

Everything in the "Non-negotiable rules" of `AGENTS.md` applies whether a person or a model wrote the text.
In particular: no invented numbers, no text aimed at the AI grader, nothing real outside the sandbox.
