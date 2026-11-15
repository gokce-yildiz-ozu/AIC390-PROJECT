# Deadline Radar

One verified deadline list from a student's emails, LMS posts and syllabi, and cited answers to school-rule
questions. Built in seven weeks for AIC 390 Prompt Engineering, Özyeğin University, Fall 2026.

The assistant **extracts** deadlines from untrusted messages, **answers** rule questions from documents with
citations, **looks up** deadlines in structured data, **acts** through one confirmed sandbox action (a calendar
reminder), and **measures** itself on a weekly scoreboard. First user: an undergraduate taking 4–6 courses.

| Team member | Role |
|---|---|
| Serap Gökçe Yıldız | Evaluation and safety lead |
| Enes Kemal Köylü | to be decided |
| Mert Bozma | to be decided |

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
| `docs/proposal/`, `docs/feedback/` | Project proposal and instructor feedback |
| `CONTRIBUTING.md` | Commands, layout, rules and conventions for the team |

## Reproducing a number

Every number in a report names its script. Check out the report's tag (`git checkout week-N`), run that script,
and compare with `results/`. Numbers that need a paid model also need your own `.env`.
