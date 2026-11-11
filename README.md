# AIC 390 team project

> Product name, use case and first customer: decided in week 1 (see `docs/STATUS.md`).

An AI assistant for one market that **answers** from documents with citations, **looks up** structured data,
**acts** through a confirmed sandbox action, and **measures** itself on a weekly scoreboard. Built in seven weeks
for AIC 390 Prompt Engineering, Özyeğin University, Fall 2026.

| Team member | Role |
|---|---|
| | Data and retrieval lead |
| | Agent and tools lead |
| | Evaluation and safety lead |

## Setup

```powershell
git clone https://github.com/gokce-yildiz-ozu/AIC390-PROJECT.git
cd AIC390-PROJECT
python -m venv .venv
.venv\Scripts\Activate.ps1                 # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env                      # then fill in LLM_API_KEY and LLM_MODEL
pytest -q
python scripts/run_baseline.py --dry-run    # offline smoke test
```

## Where things are

| Path | What |
|---|---|
| `reports/week-N.md` | Weekly reports (tagged `week-N`) |
| `eval/scoreboard.json` | Current scoreboard, written by the harness |
| `results/` | Raw outputs and summaries behind every reported number |
| `docs/course/requirements.md` | Deliverables, rules and grading, condensed |
| `docs/STATUS.md`, `docs/decisions.md` | Current state; decisions and reasons |
| `CONTRIBUTING.md` | Commands, layout, rules and conventions for the team |

## Reproducing a number

Every number in a report names its script. Check out the report's tag (`git checkout week-N`), run that script,
and compare with `results/`. Numbers that need a paid model also need your own `.env`.
