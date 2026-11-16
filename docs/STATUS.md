# Status

Short and current. Rewrite lines rather than appending a diary. Last updated: 2026-11-16.

## Now

- Product: **Deadline Radar** (own idea, D-003). Scope A: deadline extraction is the core, rule Q&A with
  citations supports it (D-004). First user: an undergraduate taking 4–6 courses.
- Week: 1 (problem and baseline). Class: Wednesdays 12:30. **Week-1 report and `week-1` tag due Tue 2026-11-17
  12:30** (R4: 24 h before class). Team target: submitted by 10:00.
- Proposal presented 2026-11-11. Instructor feedback: `docs/feedback/2026-11-11-proposal.md`. Main point: RAG
  design insufficient → response plan D-005 (proposed).
- Model: openai/gpt-oss-120b on Groq, free plan (D-006). Spend is still reported every week (R14).

## Roles

| Role | Member |
|---|---|
| Evaluation and safety lead | Serap Gökçe Yıldız |
| Data and retrieval lead | Mert Bozma |
| Agent and tools lead | Enes Kemal Köylü |

## Open questions

- What exactly did the instructor find insufficient about RAG? Confirm our reading (D-005) in the week-1
  presentation.

## Next actions (week 1)

| # | Deliverable | Owner (role) | Evidence | Status |
|---|---|---|---|---|
| 1 | Decide the two remaining roles; all members have repo access | all | this file, README | open |
| 2 | W1.1 Team agreement, signed by all three | all | `docs/team_agreement.md` | open |
| 3 | W1.2 Use case brief | agent and tools | `docs/use_case_brief.md` | done |
| 4 | W1.3 25 labelled inputs | evaluation and safety | `eval/testsets/week1_inputs.jsonl` | done |
| 5 | W1.4 Data inventory: documents and DB | data and retrieval | `docs/data_inventory.md` | open |
| 6 | W1.4 Data inventory: tools and action API sketch | agent and tools | `docs/data_inventory.md` | done |
| 7 | D-005 RAG plan detailed (corpus, metadata, stack) | data and retrieval | `docs/decisions.md` | open |
| 8 | W1.5 Baseline at temperatures 0, 0.7, 1.2 | evaluation and safety | `results/` | open |
| 9 | W1.6 Cost estimate vs measured tokens | agent and tools | `docs/cost_estimate.md` | done |
| 10 | W1.7 ≥ 5 predicted failures, each tied to a Module 1 concept | evaluation and safety | `docs/predicted_failures.md` | open |
| 11 | W1.8 README, `reports/week-1.md`, tag `week-1`, submit link | evaluation and safety | `reports/week-1.md` | open |

## Area coverage (R2: every member needs commits in ≥ 2 role areas by week 7)

| Member | data | agent | eval |
|---|---|---|---|
| Serap Gökçe Yıldız | | | |
| Enes Kemal Köylü | | | |
| Mert Bozma | | | |

## Experiments

| Date | Hypothesis | Result (value, n, CI) | Decision | Evidence |
|---|---|---|---|---|
