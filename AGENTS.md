# AGENTS.md: AIC 390 team project

Shared instructions for every coding agent (Claude Code, Cursor, Copilot, Codex) and every human on the team.

## What this repo is

A 7-week course project (AIC 390 Prompt Engineering, Özyeğin University, Fall 2026). We build one AI assistant
for one market, layer by layer: request classifier → RAG with citations → data look-up tool → write action behind
a confirmation → MCP server → agent loop, all wrapped in an evaluation harness that updates one scoreboard every
week. Grading rewards evidence: measured numbers with n, a 95% interval, and the script that produced them.

| Need | Read |
|---|---|
| Deliverable IDs, weekly requirements, course rules | `docs/course/requirements.md` (read before planning any week) |
| Current state, owners, next actions | `docs/STATUS.md` |
| Decisions and their reasons | `docs/decisions.md` |
| Work requests from the planning chat | `docs/handoffs/` |
| How we use AI tools as a team | `docs/ai-workflow.md` |

## Commands

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env               # macOS/Linux: cp; then fill in the keys
pytest -q                            # offline, never calls a paid API
ruff check . ; ruff format .
python scripts/run_baseline.py --dry-run   # W1.5 runner, offline fake model
```

## Layout

| Path | Contents |
|---|---|
| `src/aic390/` | `llm.py` (the only way to call a model), `stats.py`, `classifier/`, `rag/`, `tools/`, `agent/`, `mcp_server/` |
| `eval/` | harness, `testsets/` (frozen once used), `scoreboard.json` |
| `prompts/` | versioned prompt files `name_vN.md`; a released version is never edited, add `vN+1` |
| `data/corpus/`, `data/db/` | RAG documents and synthetic structured data |
| `sandbox/` | fake APIs; the only target of write actions |
| `results/` | committed experiment outputs: the evidence behind every reported number |
| `reports/week-N.md` | weekly reports, from `docs/weekly_report_template.md` |

## Non-negotiable rules

Breaking one of these costs the milestone or worse. Rule numbers refer to the course handbook.

1. **Never invent a number.** Every number in a report or `eval/scoreboard.json` comes from a script in this repo
   and is reproducible from the tagged commit. Not measured yet = `null`. No estimates presented as results. (R8, R18)
2. Every accuracy-type metric is reported as value, n, 95% interval (`aic390.stats.proportion_ci`) and script path.
3. **Test sets are frozen** once used in a comparison. A change means a new file version, a re-run of the old
   system on it, and a note in the report. (R9)
4. **No real personal data.** Synthetic data, or public sources with attribution and a compatible license. (R10)
5. **Write actions only hit `sandbox/` fake APIs.** No real emails, payments, bookings or messages. (R11)
6. **Secrets live only in `.env`** (gitignored). Never read, print, commit or paste a key. (R13)
7. **Never write text aimed at an AI grader or evaluator** in any file. It is prompt injection and academic
   misconduct. (R17)
8. Red-team only our own system and the one team we are assigned, only in its sandbox. (R12)
9. **Model spend is budgeted.** Before a run with more than 50 paid API calls, print calls × estimated cost and
   get a human OK. Every run logs its token usage. (R14)

## Engineering conventions

- Python ≥ 3.11. Type hints on function signatures only. Comments only where the code is not self-explanatory.
- Use current library APIs. If unsure whether an API is current, check the installed version's docs first.
- Feature code never calls a provider SDK directly: go through `aic390.llm` so tokens, latency and model are logged.
- Every result file records: git commit, prompt version, model, temperature, test set path, n.
- Experiments change one thing at a time on a fixed test set; outputs go to `results/<YYYY-MM-DD>_<slug>/`
  (`config.json`, raw outputs, `summary.json`).
- Tests use `FakeClient`; no test may call a paid API.
- Commit prefix = role area: `[data]`, `[agent]`, `[eval]`, plus `[docs]`, `[infra]`. We build the contributions
  table from these, and every member needs commits in at least two of the three role areas (R2).
- Changes inside another lead's area go through a pull request that the area lead reviews.
- Weekly: copy `docs/weekly_report_template.md` to `reports/week-N.md`, tag the commit `week-N`, submit the link
  at least 24 hours before class. Keep every heading; at most 1,500 words excluding tables and scoreboard.
