# Weekly report

| Field | Value |
|---|---|
| Team | Deadline Radar |
| Use case | Own idea, accepted by the instructor on 2026-11-11 (D-003) |
| Week | 3 |
| Repository | https://github.com/gokce-yildiz-ozu/AIC390-PROJECT |
| Commit tag | week-3 |
| Presenter | Mert Bozma (rotation in `docs/team_agreement.md` §2) |
| Members and roles | Mert Bozma (data and retrieval lead); Enes Kemal Köylü (agent and tools lead); Serap Gökçe Yıldız (evaluation and safety lead) |

## 1. Summary

Week 3 replaced the stub with real retrieval: hybrid search with a reranker over 3,889 documents and 11,388 chunks. The most important number: the gold passage is in the top 5 for 29/30 retrieval questions, 0.967 [0.833, 0.994]. End to end with real search and `answer_v2`, 38/42 = 0.905 [0.779, 0.962]; our pre-written rule keeps `answer_v1` as the default, since `answer_v2` lost one abstention. On the search cases, real search could not be told apart from the stub. Both retrieval failures are Turkish questions on English regulations; we test query translation in week 4.

## 2. Deliverables

| ID | Status | Evidence | Note |
|---|---|---|---|
| W3.1 | done | [`data/corpus/`](../data/corpus/), [`scripts/generate_bulk_corpus.py`](../scripts/generate_bulk_corpus.py), [`results/2026-11-23_bulk-corpus/`](../results/2026-11-23_bulk-corpus/), [`docs/decisions.md`](../docs/decisions.md) D-008 | 10 core documents, reviewed (`43e105b`); a seeded generator (seed 20261122) adds 3,879 documents for 900 invented courses: 1,158 syllabi (258 with a revised version) and 2,721 announcements. 11,388 chunks (en 9,157, tr 2,231). Metadata: `source`, `version`, `valid_from`, `audience`. `audience` is recorded but not enforced in search yet (week 4) |
| W3.2 | done | [`src/aic390/rag/chunking.py`](../src/aic390/rag/chunking.py), [`data/chunks.jsonl`](../data/chunks.jsonl), [`scripts/chunk_stats.py`](../scripts/chunk_stats.py), [`results/2026-11-24_chunk-stats/`](../results/2026-11-24_chunk-stats/) | One chunk per `##` section, which is also the citation unit; a section over 200 words would be split, none is. Words per chunk: median 15, p90 36, max 55 (n = 11,388). No overlap: each section is one self-contained rule, and gold passages are (`doc_id`, `section`), so chunk settings never change the test set |
| W3.3 | done | [`src/aic390/rag/search.py`](../src/aic390/rag/search.py), [`docs/decisions.md`](../docs/decisions.md) D-007 | BM25 (`bm25s`) and `BAAI/bge-m3` (cosine), reciprocal rank fusion k = 60 over the top 20 of each, then `BAAI/bge-reranker-v2-m3` on the fused top 20. In memory, no database (D-007) |
| W3.4 | done | [`prompts/answer_v2.md`](../prompts/answer_v2.md), [`src/aic390/agent/answer.py`](../src/aic390/agent/answer.py), [Run B](../results/2026-11-23_e2e_w3-real-ansv2_openai-gpt-oss-120b/), [Run A vs B](../results/2026-11-23_compare_w3-real-ansv1_vs_w3-real-ansv2_common-ids/) | `answer_v2`: `[n]` after every fact, renumbered in code to the source order; three fixed replies for abstaining. Fixed replies in `answer_v2` (Run B); the default `answer_v1` does not give them with real search, because no search in Run B returned zero hits. Default and demo: `answer_v1` |
| W3.5 | done | [`eval/retrieval.py`](../eval/retrieval.py), [`eval/testsets/retrieval_questions.jsonl`](../eval/testsets/retrieval_questions.jsonl), [`results/2026-11-23_retrieval_hybrid-rerank/`](../results/2026-11-23_retrieval_hybrid-rerank/) | 30 questions written and frozen by the evaluation lead, not the corpus author; gold unit (`doc_id`, `section`). hit@5 29/30 = 0.967 [0.833, 0.994]; Experiment 1 |
| W3.6 | done | [`eval/faithfulness.py`](../eval/faithfulness.py), [`prompts/faithfulness_v1.md`](../prompts/faithfulness_v1.md), [`results/2026-11-23_faithfulness-v1/`](../results/2026-11-23_faithfulness-v1/) | 13 claims from 7 Run B answers: fewer than 20, so all were labelled and the intervals are wide. Judge kappa 0.629 against each rater, bootstrap 95% [0.000, 1.000] (threshold 0.6 met on the point estimate); the raters agree 13/13. Rater 1 read the Run B note on w1-21 before labelling. <!-- 13 iddia / 7 vaka (< 20: plan kuralı); iki kör insan etiketçi; rater 1 w1-21'in Run B yorumunu etiketlemeden önce okudu (söyle) --> |
| W3.7 | done | [dense](../results/2026-11-23_retrieval_dense-rerank/), [BM25](../results/2026-11-23_retrieval_bm25-rerank/), [no reranker](../results/2026-11-23_retrieval_hybrid-norerank/), [hybrid vs dense](../results/2026-11-23_retrieval-compare_hybrid-rerank_vs_dense-rerank_hit_at_5/), [rerank on vs off](../results/2026-11-23_retrieval-compare_hybrid-rerank_vs_hybrid-norerank_hit_at_1/) | Two ablations, one change each; BM25 only as an extra row. Both equal under the rules written before the runs; Experiments 2 and 3 |
| W3.8 | done | §5 below, [Run A](../results/2026-11-23_e2e_w3-real-ansv1_openai-gpt-oss-120b/), [stub vs real](../results/2026-11-23_compare_w25-v1-a_vs_w3-real-ansv1_common-ids/) | 7 failures, one rule: gold section not in the top k → retrieval (3); gold there but the answer wrong → generation (2); intent wrong before search → prompt (2). Stub search serves as a near-oracle; see §5 |
| Product track | done | §7, [first interview](../docs/interviews/2026-11-23_student_e.md), [second interview](../docs/interviews/2026-11-24_student_g.md) | Two interviews with students |

## 3. Scoreboard

```json
{
  "week": 3,
  "test_set_size": 42,
  "e2e_accuracy": {
    "value": 0.905,
    "ci95": [
      0.779,
      0.962
    ],
    "n": 42,
    "script": "eval/run_e2e.py"
  },
  "abstention_correct": {
    "value": 0.833,
    "ci95": [
      0.436,
      0.97
    ],
    "n": 6,
    "script": "eval/run_e2e.py"
  },
  "unsupported_claims": {
    "value": 0.077,
    "ci95": [
      0.014,
      0.333
    ],
    "n": 13,
    "script": "eval/faithfulness.py",
    "source": "judge"
  },
  "hit_at_5": {
    "value": 0.967,
    "ci95": [
      0.833,
      0.994
    ],
    "n": 30,
    "script": "eval/retrieval.py"
  },
  "mrr": {
    "value": 0.933,
    "ci95": [
      0.85,
      1.0
    ],
    "n": 30,
    "script": "eval/retrieval.py"
  },
  "task_success": null,
  "pass_k": null,
  "injection_success": {
    "value": 0.0,
    "ci95": [
      0.0,
      0.562
    ],
    "n": 3,
    "script": "scripts/run_injection_tests.py",
    "note": "carried from week 2 (W2.8, stub search); not re-measured with real search",
    "measured_in_week": 2
  },
  "cost_per_task_usd": 0.000413,
  "latency_p50_s": 1.942,
  "spend_week_usd": 0.0,
  "spend_total_usd": 0.0
}
```

Notes: `e2e_accuracy`, `abstention_correct`, cost and latency come from Run B (real hybrid search, seed table, `answer_v2`); the default prompt stays `answer_v1` (Experiment 5). `unsupported_claims` is the judge's rate (kappa at least 0.6 against both raters, Experiment 6); both human raters marked 2/13 unsupported. `injection_success` is carried from week 2 (W2.8, stub search) and was measured on the attempts the fix was designed for, so it is in-sample. Cost uses list prices; actual spend was 0 on the free plan.

Changes to any test set this week: none

## 4. Experiments

Hypotheses and decision rules were written in [`docs/STATUS.md`](../docs/STATUS.md) (Experiments) before each run.

### Experiment 1: retrieval baseline, main configuration (W3.5)

- **Hypothesis:** hit@5 ≥ 0.80 on the 30 frozen questions (the week-2 target).
- **Change:** none; a measurement of the main configuration: hybrid + reranker, 11,388 chunks, no course filter.
- **Result:** hit@5 29/30 = 0.967 [0.833, 0.994], hit@1 27/30 = 0.900 [0.744, 0.965], MRR 0.933 [0.850, 1.000] (bootstrap). Turkish hit@5 11/12, English 18/18; the miss is r02 (§5). Median search 0.256 s on a laptop GPU.
- **Decision:** target met; even the lower bound is above 0.80. Limit: the bulk documents are templated, so they are easier distractors than a real school's.

### Experiment 2: hybrid vs dense only (W3.7, ablation 1)

- **Hypothesis:** hybrid beats dense on the 7 confusable questions; dense beats BM25 on the 12 Turkish ones.
- **Change:** `mode = dense` instead of hybrid; reranker on in both.
- **Result:** dense hit@5 28/30 = 0.933 [0.787, 0.982]. McNemar b = 1 (r09), c = 0, p = 1.0; with b + c < 6 no split can reach p < 0.05. Confusable: 7/7 in both. Turkish hit@5: dense 10/12, BM25 8/12; BM25 alone 25/30 = 0.833 [0.664, 0.927].
- **Decision:** equal, so hybrid stays (D-007). First half not supported; second half holds (descriptive).

### Experiment 3: reranker on vs off (W3.7, ablation 2)

- **Hypothesis:** the reranker raises hit@1 and MRR more than hit@5.
- **Change:** `rerank = False`; hybrid in both.
- **Result:** without it, hit@1 25/30 = 0.833 [0.664, 0.927], MRR 0.879 [0.774, 0.973], hit@5 unchanged (29/30). McNemar on hit@1: b = 3 (r15, r17, r29), c = 1 (r24), p = 0.625. Cost +0.249 s per query (GPU).
- **Decision:** equal, and under the 1.0 s rule written before the run, so the reranker stays. In r24 a near-duplicate of Article 14 went first (§5).

### Experiment 4: stub search vs real search on the 19 search cases (Run A, W3.8)

- **Hypothesis:** Accuracy with real search is at most the stub's, because the stub returns only the gold sections.
- **Change:** One change against week 2's `w25-v1-a`: `--search real`. All prompts v1, seed table, T = 0; only the 19 cases that use search.
- **Result:** 17/19 = 0.895, Wilson 95% [0.686, 0.971], against 16/19 = 0.842 [0.624, 0.945] with the stub. Exact McNemar b = 1 (w1-11), c = 2 (w1-08, w1-21), p = 1.0 ([comparison](../results/2026-11-23_compare_w25-v1-a_vs_w3-real-ansv1_common-ids/)).
- **Decision:** Not supported, and no difference either. w1-11 is a retrieval failure: Article 12 is not in the top 5 (§5). w1-08 also flipped between two week-2 runs, so with one run each, w1-08 and w1-21 cannot be told apart from run-to-run noise.

### Experiment 5: answer_v1 vs answer_v2 with real search (Run B, W3.4)

- **Hypothesis:** `answer_v2` is no worse on accuracy, abstains at least as often, and every answer carries valid `[n]` markers.
- **Change:** `--prompts answer=answer_v2` against Run A; 42 cases, real search.
- **Result:** 38/42 = 0.905 [0.779, 0.962]. Common 19: 15/19 vs 17/19, exact McNemar b = 2 (w1-19, w1-21), c = 0, p = 0.5. `abstention_correct` 5/6 = 0.833 [0.436, 0.970] vs 6/6 = 1.000 [0.610, 1.000]; `false_abstentions` 1/34 = 0.029 [0.005, 0.149]. All 7 answered rule questions carry valid markers.
- **Decision:** `answer_v1` stays the default, also in the demo: the rule, written before the run, does not allow lower abstention. The lost case is w1-21 (hallucination log #14); w1-19 is classifier noise. Six cases and one run per prompt do not show that `answer_v1` is better.

### Experiment 6: faithfulness judge vs two blind raters (W3.6)

- **Hypothesis:** The judge agrees with each of two blind raters at kappa ≥ 0.6.
- **Change:** A measurement, no comparison. Judge `qwen/qwen3.8-27b`, T = 0, `faithfulness_v1`, on all 13 claims of Run B's 7 answered rule questions. The raters committed their labels before the judge ran.
- **Result:** Kappa 0.629 against each rater, bootstrap 95% [0.000, 1.000] (undefined in 227 of 2,000 resamples); the raters agree 13/13. The one disagreement, w1-12#2, cites the wrong source: raters unsupported, judge supported. Unsupported: judge 1/13, raters 2/13.
- **Decision:** Met on the point estimate, so `unsupported_claims` comes from the judge. But the gate rests on that one claim (agreement there gives kappa 1), and it is the error type the week-6 citation check targets (§5).

## 5. Failure analysis

| # | Input (short) | What happened | Root cause | Fix (done or planned) |
|---|---|---|---|---|
| 1 | w1-11 (TR, make-up exam rule); same pattern in r02 (TR, make-up week, W3.5) | Gold `regulation-article-12` not in the top 5; all five are bulk `Attendance` sections. The model abstained: Run B's only false abstention (1/34). With stub search the case passes. r02: gold section not in the top 10. Both are Turkish questions on English regulations | retrieval | Planned, week 4: translate the query before search; measured on hit@5 for the Turkish questions (now 11/12) and on w1-11. Not measured yet |
| 2 | w1-21 (EN, "Can the instructor move the HW2 deadline? Can I object?"); expected: abstain | Run B (`answer_v2`) answered: it stretched Article 14's late-work rule to deadline changes and cited it as [1]. The refusal rule for this kind of question is in the prompt, but the model did not follow it; the code check only asks for a valid source number, not that the source supports the sentence ([hallucination log #14](../docs/hallucination_log.md)) | generation | Planned, week 6 (hardening): a code check that the cited source supports the sentence, not only that the number is valid; measured on `unsupported_claims` and abstention. `answer_v1` stays the default (Run B rule), but it is not shown to be safer here: it answered this case in 3 of 4 W2.5 runs (log #13); in Run A (real search) it abstained correctly |
| 3 | w1-20 (TR, dorm application deadline); w1-19 (EN, "45 on the midterm, will I pass?") | The classifier says `other`, so the student gets the fixed out-of-scope reply with no pointer to where to ask (no invented date). w1-20: 6 of 6 runs (4 W2.5 runs, Run A, Run B). w1-19: `rule_question` in Run A, `other` in Run B, same `classifier_v1`, T = 0. Recurring: [week-2 failure 1](week-2.md) | prompt | Planned, week 4 (unchanged from week 2): `classifier_v2`, one change to the `rule_question` definition, measured on the 42 cases and on `heldout_v2` |

**W3.8: every failure this week, labelled.**
We compared each end-to-end failure with stub search, which searches only the gold sections: close to an ideal retriever, but not a full oracle, since it still matches by keywords. If the gold section was missing from the top k, we labelled the failure retrieval; if it was there but the answer was wrong, generation. `w1-21` has no gold section: the right topic was retrieved, the documents contain no answer, and the model answered instead of abstaining, so it is also generation. Intent errors (`w1-19`, `w1-20`) happen before search and never reach retrieval or generation, so we label them prompt.

| Case | Run | Label | Evidence |
|---|---|---|---|
| w1-11 | Run A, Run B | retrieval | Trace: gold not in top 5; [Run A](../results/2026-11-23_e2e_w3-real-ansv1_openai-gpt-oss-120b/), [Run B](../results/2026-11-23_e2e_w3-real-ansv2_openai-gpt-oss-120b/) |
| r02 | W3.5 | retrieval | Gold not in top 10; [W3.5](../results/2026-11-23_retrieval_hybrid-rerank/) |
| w1-21 | Run B | generation | [Hallucination log #14](../docs/hallucination_log.md), [Run B](../results/2026-11-23_e2e_w3-real-ansv2_openai-gpt-oss-120b/) |
| w1-12 | Run B (W3.6) | generation | Claim 2 cites [2] (Article 14), which does not state it; the content is in [1], so the citation points to the wrong source. Both raters: unsupported; judge: supported; [W3.6](../results/2026-11-23_faithfulness-v1/) |
| w1-20 | stub, Run A, Run B | prompt | Intent `other` in all runs; [week-2 §5](week-2.md) |
| w1-19 | Run B | prompt (run-to-run noise) | Run A `rule_question`, Run B `other`; [STATUS](../docs/STATUS.md) |
| r24 | W3.7 | retrieval (rank, not recall) | Top 1 with the reranker is `econ101-late-policy`, a copy of Article 14 in the corpus; [rerank on vs off](../results/2026-11-23_retrieval-compare_hybrid-rerank_vs_hybrid-norerank_hit_at_1/) |

Even at T = 0, the same configuration gave different outcomes across runs: `w1-19` flipped between `rule_question` and `other` under the same classifier, while `w1-21` abstained in only one of four W2.5 runs with the same answer prompt. So a single run per configuration cannot separate prompt effects from run-to-run noise; from week 4 we will evaluate each configuration across multiple runs.

## 6. Response to last week's feedback

Weeks 2 and 3 are presented in the same session, so there is no new feedback after week 2; the table lists the [week-1 points](../docs/feedback/2026-11-18-week1.md) this week closes.

| Feedback point | What we changed | Evidence |
|---|---|---|
| The corpus should be at least 10,000 chunks (3c) | 11,388 chunks, reached by adding documents (10 core + 3,879 generated), not by shrinking chunks (D-008) | [`results/2026-11-23_bulk-corpus/`](../results/2026-11-23_bulk-corpus/), D-008 |
| The live demo must show the classifier and RAG (3) | The demo runs hybrid search on the full corpus and shows the BM25 and dense ranks, the reranker score and the index load time; search time is measured | [`app/demo.py`](../app/demo.py), [`results/2026-11-23_demo-search-timing_cpu/`](../results/2026-11-23_demo-search-timing_cpu/) |
| Show the architecture in detail, and our data (3b) | Retrieval rows in the architecture (`0b7df66`) and the search box at 11,388 chunks with measured latency (`8fe2a9d`) | [`docs/architecture.md`](../docs/architecture.md) |

## 7. Product track

**Interview (Enes), 2026-11-23: first-year business student, 6 courses.** Friends remind them of deadlines on WhatsApp; dates also come from the LMS and email. The last homework they missed was left to the last moment and cost about 3% of the grade ("not sure"). They might pay 100–200 TL a month, but would rather have the school pay and the tool read the LMS. Fears: private information leaking, and emails sent to instructors in their name. Most surprising: the date was known; the problem was putting it off, and they want several reminders that stop once they say the work is done. Our design has one reminder, 24 hours before. We keep sources and confirmation before any action; a "done" mark and more than one reminder are proposed for the reminder action; the team has not decided yet. Notes and limits: [`docs/interviews/2026-11-23_student_e.md`](../docs/interviews/2026-11-23_student_e.md).

**Interview (Gökçe), 2026-11-24: second-year industrial engineering student, by WhatsApp.** Their last homework was posted only on the last page of a slide deck; they learned of it on the due date. The first interviewee knew the date and put the work off; this one never saw it. Both rely on WhatsApp for updates, want the school to pay, and would probably stop using it after one wrong date. Our corpus has no slides: an open gap the team has not decided on yet. Notes: [`docs/interviews/2026-11-24_student_g.md`](../docs/interviews/2026-11-24_student_g.md).

## 8. Contributions

| Member | Role | What they did this week | Commits or files | Hours |
|---|---|---|---|---|
| Serap Gökçe Yıldız | Evaluation and safety lead | Experiment plan rows in STATUS before the runs; faithfulness tool and labelling sheet; W3.6 labels (rater 1), judge run and kappa; Run A vs stub and Run B vs Run A comparisons; week-3 scoreboard script; report skeleton, §5, §10 | 15 commits; `eval/faithfulness.py`, `prompts/faithfulness_v1.md`, `scripts/write_week3_scoreboard.py`, `results/2026-11-23_faithfulness-v1/`, `results/2026-11-23_compare_*`, `reports/week-3.md` | 5 |
| Enes Kemal Köylü | Agent and tools lead | `answer_v2` (W3.4); search calls logged in the trace for W3.8; `compare.py --common-ids`; demo on the full corpus with hybrid search, replays and search timing; failed model replies no longer shown as "no deadline"; hallucination log #14; one customer interview | `prompts/answer_v2.md`, `src/aic390/agent/`, `eval/compare.py`, `app/demo.py`, `scripts/time_demo_search.py`, `results/2026-11-23_demo-search-timing_cpu/`, `docs/hallucination_log.md`, `docs/interviews/` | 7 |
| Mert Bozma | Data and retrieval lead | Seeded bulk generator and its tests (D-008, 11,388 chunks); course filter keeps the general documents; `eval/retrieval.py` and `scripts/chunk_stats.py`; W3.5 baseline and both W3.7 ablations; Run A and Run B on the GPU laptop; architecture retrieval rows; D-007 and D-008 accepted; W3.6 rater 2 | `scripts/generate_bulk_corpus.py`, `data/corpus_bulk/`, `src/aic390/rag/`, `eval/retrieval.py`, `results/2026-11-23_retrieval_*`, `results/2026-11-23_e2e_w3-*`, `scripts/chunk_stats.py` | 6 |

## 9. AI tools used

| Tool | Used for |
|---|---|
| Claude (claude.ai, planning chat) | Planning the week and the experiments, reviewing our results and this report against the handbook, the report skeleton with the facts each section needs, a helper script for the W3.6 labelling sheet (not in the repository), the English summary and format of the second interview's notes from the interviewee's Turkish answers, and drafting or editing parts of this report from our results (Summary, Experiments 4 and 6, notes in §2, §6, §8 and §10), which we reviewed |
| Claude Code (VS Code and desktop app) | Writing and testing code (faithfulness tool, week-3 scoreboard script, search calls in the trace, demo) and preparing commits that each of us reviewed and made; for Enes's parts also: drafting Experiment 5, the W3.4 note, the first interview's summary in §7, the §8 row and hallucination log #14, suggesting the first interview's questions and translating its notes from the Turkish answers |

All W3.6 labels came from the two human raters; no label came from a model. The faithfulness judge is part of the measured system, not a writing aid.

## 10. Next week

**Week-2 targets and what happened** ([week-2 §10](week-2.md))

| Week-2 target | Week-3 result | Status |
|---|---|---|
| `hit_at_5` ≥ 0.80 with hybrid + reranker | 29/30 = 0.967 [0.833, 0.994]; [W3.5](../results/2026-11-23_retrieval_hybrid-rerank/) | Met |
| Hybrid beats BM25 on Turkish questions | TR hit@5: hybrid 11/12, dense 10/12, BM25 8/12 (descriptive, no test) | Met |
| Accuracy with real search no worse than stub | 17/19 vs 16/19, McNemar b = 1, c = 2, p = 1.0; [Run A](../results/2026-11-23_e2e_w3-real-ansv1_openai-gpt-oss-120b/) | No difference detected (p = 1.0); real search one case higher |
| `unsupported_claims` ≤ 0.10 | 1/13 = 0.077 [0.014, 0.333] (judge), n = 13; both raters 2/13; [W3.6](../results/2026-11-23_faithfulness-v1/) | Judge: met (1/13). Raters: not met (2/13). n = 13 cannot decide |
| Intent errors ≤ 1 (`classifier_v2`, `item_key`, `heldout_v2`) | Not run this week; 2 errors in Run B (w1-19, w1-20) | Week 4 |

| Priority | Metric it should move | Expected change |
|---|---|---|
| 1. W4.1–W4.4: three tools, a loop with step, token and time limits, 10 multi-step tasks with traces | Task success, steps, cost per task (new keys) | First measurement: traces for all 10 tasks; the loop stops within its limits on every task |
| 2. `classifier_v2`: one change to the `rule_question` definition | Intent errors on the 42 cases and `heldout_v2` | 2 (Run B) → ≤ 1 |
| 3. Translate Turkish queries before search | TR hit@5; w1-11; false abstentions | 11/12 → ≥ 11/12 with w1-11 passing; 1/34 → 0/34 |
