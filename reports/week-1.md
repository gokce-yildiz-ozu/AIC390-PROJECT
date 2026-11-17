# Weekly report

| Field | Value |
|---|---|
| Team | Deadline Radar |
| Use case | Own idea, accepted by the instructor on 2026-11-11 (D-003) |
| Week | 1 |
| Repository | https://github.com/gokce-yildiz-ozu/AIC390-PROJECT |
| Commit tag | week-1 |
| Presenter | Serap Gökçe Yıldız |
| Members and roles | Mert Bozma (data and retrieval lead); Enes Kemal Köylü (agent and tools lead); Serap Gökçe Yıldız (evaluation and safety lead) |

## 1. Summary

TODO (Gökçe)

## 2. Deliverables

| ID | Status | Evidence | Note |
|---|---|---|---|
| W1.1 | done | [`docs/team_agreement.md`](../docs/team_agreement.md) | Signed by all three in their own commits |
| W1.2 | done | [`docs/use_case_brief.md`](../docs/use_case_brief.md) | TODO (Enes) |
| W1.3 | done | [`eval/testsets/week1_inputs.jsonl`](../eval/testsets/week1_inputs.jsonl), format in [`eval/testsets/README.md`](../eval/testsets/README.md) | 25 inputs, each labelled with ingredients and an expected outcome |
| W1.4 | done | [`docs/data_inventory.md`](../docs/data_inventory.md) | TODO (Mert: documents, database; Enes: tools, action API) |
| W1.5 | done | [`results/2026-11-16_baseline_openai-gpt-oss-120b/`](../results/2026-11-16_baseline_openai-gpt-oss-120b/), [`results/2026-11-16_baseline-t0-repeat_openai-gpt-oss-120b/`](../results/2026-11-16_baseline-t0-repeat_openai-gpt-oss-120b/), [`scripts/run_baseline.py`](../scripts/run_baseline.py), [`scripts/analyze_week1.py`](../scripts/analyze_week1.py) | 75 calls (25 × T = 0, 0.7, 1.2) plus a second run at T = 0; every output hand-labelled |
| W1.6 | done | [`docs/cost_estimate.md`](../docs/cost_estimate.md), [`scripts/cost_breakdown.py`](../scripts/cost_breakdown.py) | TODO (Enes) |
| W1.7 | done | [`docs/predicted_failures.md`](../docs/predicted_failures.md) | Written before the baseline (commit `3bbdb25`); thresholds unchanged since |
| W1.8 | done | [`README.md`](../README.md), tag `week-1` | |

## 3. Scoreboard

```json
{
  "week": 1,
  "test_set_size": 25,
  "e2e_accuracy": {"value": 0.16, "ci95": [0.064, 0.347], "n": 25, "script": "scripts/analyze_week1.py"},
  "abstention_correct": {"value": 0.333, "ci95": [0.061, 0.792], "n": 3, "script": "scripts/analyze_week1.py"},
  "unsupported_claims": null,
  "hit_at_5": null,
  "mrr": null,
  "task_success": null,
  "pass_k": null,
  "injection_success": {"value": 1.0, "ci95": [0.342, 1.0], "n": 2, "script": "scripts/analyze_week1.py"},
  "cost_per_task_usd": 0.000289,
  "latency_p50_s": 1.109,
  "spend_week_usd": 0,
  "spend_total_usd": 0
}
```

Changes to any test set this week: none (first test set).

TODO (Gökçe): basis of each number and why Wilson intervals.

## 4. Experiments

### Experiment 1: Temperature (W1.5)

- **Hypothesis:** TODO
- **Change:** TODO
- **Result:** TODO
- **Decision:** TODO

### Experiment 2: Repeat run at T = 0

- **Hypothesis:** TODO
- **Change:** TODO
- **Result:** TODO
- **Decision:** TODO

### Experiment 3: Predicted failures P1–P6 (W1.7)

- **Hypothesis:** TODO
- **Change:** TODO
- **Result:** TODO
- **Decision:** TODO

## 5. Failure analysis

| # | Input (short) | What happened | Root cause | Fix (done or planned) |
|---|---|---|---|---|
| 1 | TODO | | | |
| 2 | TODO | | | |
| 3 | TODO | | | |

## 6. Response to last week's feedback

Feedback from the proposal session on 2026-11-11 ([`docs/feedback/2026-11-11-proposal.md`](../docs/feedback/2026-11-11-proposal.md)).

| Feedback point | What we changed | Evidence |
|---|---|---|
| The idea is accepted as our project | TODO | [`docs/decisions.md`](../docs/decisions.md) D-003 |
| RAG design is insufficient | TODO (Mert) | [`docs/decisions.md`](../docs/decisions.md) D-005, [`docs/data_inventory.md`](../docs/data_inventory.md) §1 |
| Scope and who pays are our choice | TODO | [`docs/decisions.md`](../docs/decisions.md) D-004 |
| Any model may be used | TODO | [`docs/decisions.md`](../docs/decisions.md) D-006, [`config/prices.json`](../config/prices.json) |

## 7. Product track

TODO (Gökçe)

## 8. Contributions

| Member | Role | What they did this week | Commits or files | Hours |
|---|---|---|---|---|
| Serap Gökçe Yıldız | Evaluation and safety lead | TODO | `src/aic390/` (llm, stats, scoreboard, cost), `scripts/run_baseline.py`, `scripts/analyze_week1.py`, `tests/`, `eval/testsets/week1_inputs.jsonl`, `results/2026-11-16_*`, `docs/predicted_failures.md`, `docs/decisions.md` (D-006), `docs/team_agreement.md` | TODO |
| Enes Kemal Köylü | Agent and tools lead | TODO (Enes) | `docs/use_case_brief.md`, `docs/cost_estimate.md`, `scripts/cost_breakdown.py`, `docs/data_inventory.md` §3 | TODO |
| Mert Bozma | Data and retrieval lead | TODO (Mert) | `docs/data_inventory.md` §1–2 and §4, `docs/decisions.md` (D-005 detail) | TODO |

## 9. AI tools used

| Tool | Used for |
|---|---|
| TODO | |

## 10. Next week

| Priority | Metric it should move | Expected change |
|---|---|---|
| 1 | TODO | |
| 2 | TODO | |
| 3 | TODO | |
