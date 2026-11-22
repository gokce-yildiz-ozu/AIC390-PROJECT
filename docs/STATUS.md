# Status

Short and current. Rewrite lines rather than appending a diary. Last updated: 2026-11-22.

## Now

- Product: **Deadline Radar** (own idea, D-003). Scope A: deadline extraction is the core, rule Q&A with
  citations supports it (D-004). First user: an undergraduate taking 4–6 courses.
- Week: **2 and 3 together** (instructor, 2026-11-18). Next class Wed 2026-11-25 12:30. Two reports, two tags,
  both links submitted by **Tue 2026-11-24 12:30** (R4). Team target: Tue 10:00.
- **Live demo on 2026-11-25 must include RAG and the request classifier** (`docs/feedback/2026-11-18-week1.md`).
- Week 2 done (`reports/week-2.md`): W2.5 kept `extract_v1` (three versions equal, token rule); held-out 6/13; judge
  kappa 0.80. Week 3 waits on the bulk corpus and the index (data and retrieval); W3.4 code is in (`answer_v2`).
- Model: openai/gpt-oss-120b on Groq, free plan (D-006). Retrieval stack: D-007; corpus of ≥ 10,000 chunks: D-008 (both proposed).

## Demo plan (2026-11-25)

The instructor asked for the classifier, extraction and RAG in the live demo, and to see our architecture and data.
The screen shows every step: classifier JSON (valid or not, retries) → route → extraction with dates computed in
`dates.py`, or retrieved passages with BM25, dense, fused and reranker positions → answer with numbered citations,
or the fixed "not in the documents" reply. The instructor asked for the architecture **in detail**: the diagram in
`docs/architecture.md` numbers every component, and the demo screen shows the same numbers, so each demo step
points at a box. Slides: the architecture (diagram plus one table of components), one data slide (core and bulk
corpus, ≥ 10,000 chunks, D-008). Every member can explain every box (R5).

| # | Scenario | Input | Shows |
|---|---|---|---|
| A | Rule question where a course policy overrides the regulation | w1-12 | Two citations, precedence |
| B | Deadline moved relative to a date the message does not state ("HW3 extended by one week") | new case | Retrieval inside extraction (D-005): original date retrieved, new date computed in code |
| C | Unanswerable | w1-20 | Abstention |
| D | Confusable course codes | w1-13 | Why hybrid: BM25 versus dense ranks |
| E | Injection in an email body | a W2.8 attempt | Trust from sender metadata, body treated as data |
| F | Relative date with two readings | w1-02 | `dates.py` flags both dates and asks |

Plus questions the instructor chooses: rehearsed on Mon 2026-11-23 with 5 unseen questions per member. Replay mode
exists only as a fallback if the network fails; if used, the screen says "replay" and we say so.

## Interfaces (frozen Thu 2026-11-19 12:00; change only by telling the other two)

| # | Interface | Owner | Contract |
|---|---|---|---|
| 1 | Classifier output | agent and tools | `{"intent": "deadline_message \| rule_question \| lookup \| reminder \| other", "course": "CS-301" \| null, "urgency": "high \| normal", "multi_step": true \| false}`; `multi_step` added Fri 2026-11-20: true when the student asks for several things, and intent is then the first one (w1-22) |
| 2 | `rag.search(query, course=None, doc_type=None, k=5, as_of=None)` | data and retrieval | List of `{doc_id, section, version, text, score, chunk_id, bm25_rank, dense_rank, rerank_score}`; `as_of` keeps only the version valid at that time (CS-310 v1 / v2) |
| 3 | Documents | data and retrieval | `data/corpus/<doc_id>.md`, YAML front matter `doc_id, title, course, doc_type, version, valid_from, language, audience, source, reviewed`; `##` headings are the citation sections |
| 4 | Harness entry points | evaluation and safety ← agent and tools | `aic390.agent.pipeline.run_case(case, client, search=None, table=None, prompts=None)` returns the interface 5 fields plus `answer_text`, `classifier`, `valid`, `trace`. Parts: `classify(case, client)`; `extract(case, client, table=None, search=None, prompt_version)` → `{deadlines, ask_user, untrusted_flag, action, sources, dropped, valid, trace}` (`dropped`: rows the model returned for another course than the message's, not applied; added Sun 2026-11-22 after W2.8 inj-01); `answer(case, client, search=None, table=None, intent, course)` → `{text, sources, abstain, count, deadlines, ask_user, action, answer_language, valid, trace}`. `search` defaults to the stub in `aic390/agent/search_stub.py` until interface 2 is ready; `table` to `data/db/deadlines_seed.jsonl`. `prompts` maps a step (`classifier`, `extract`, `answer`, `lookup`) to a prompt version, e.g. `{"extract": "extract_v2"}`; a step left out uses its default (v1), an unknown step raises `ValueError`; the version each call used is in `trace[].prompt_version`. `answer_v2` (W3.4, Sun 2026-11-22): the answer cites `[n]` after every fact and the code renumbers the markers so `[1]` is `sources[0]`, `[2]` is `sources[1]`; an abstention is one of three fixed replies (`not_in_documents`, `grade_prediction`, `legal_interpretation`, English or Turkish), and an answer with no valid marker is replaced by the `not_in_documents` reply. The default stays `answer_v1` until W2.5 is done; W3.4 runs pass `--prompts answer=answer_v2`. Agreed Fri 2026-11-20; `prompts` added Sun 2026-11-22 |
| 5 | Pipeline output | agent and tools → evaluation and safety | Same fields as `expected` in `eval/testsets/week2_cases.jsonl`; the date fields of each deadline row (`due_date, due_time, due_candidates`, plus `ask_user`) come from `aic390.dates.resolve`, never from the model. Weekday modifiers: none, `next` (two candidates, w1-02), `next_week` ("haftaya", one date, w2-09); added Fri 2026-11-20 |

New packages go into `pyproject.toml` in one commit by the agent and tools lead on Thu 2026-11-19 morning
(`pydantic`, `pyyaml`, `bm25s`, `sentence-transformers`, `streamlit`; retrieval and demo packages as optional
extras so CI stays light).

## Roles

| Role | Member |
|---|---|
| Evaluation and safety lead | Serap Gökçe Yıldız |
| Data and retrieval lead | Mert Bozma |
| Agent and tools lead | Enes Kemal Köylü |

## Open questions

- None open with the instructor.

## Next actions (weeks 2 and 3)

Parts for `week-2` by **Sun 22 18:00**, tag `week-2` Sun 23:59. Parts for `week-3` by **Mon 23 20:00**, tag
`week-3` Mon 23:59. Both links submitted Tue 24 10:00. The evaluation and safety lead assembles both reports.

| # | Deliverable | Owner (role) | Evidence | Due |
|---|---|---|---|---|
| 1 | Feedback written down; D-007 confirmed; interfaces 1–4 frozen; packages commit | all | `docs/feedback/2026-11-18-week1.md`, `docs/decisions.md`, this file | Thu 19, 12:00 |
| 2 | W2.1 Request classifier (schema, T = 0, validation, retry) | agent and tools | `src/aic390/classifier/` | Thu 19 · ✓ |
| 3 | W2.3 Test set ≥ 40 cases, structured expected outputs (draft) | evaluation and safety | `eval/testsets/week2_cases.jsonl` | Thu 19 · ✓ |
| 4 | W3.1 10 core documents, reviewed ✓ (`43e105b`); bulk generator to ≥ 30 documents and ≥ 10,000 chunks (D-008), course announcements with `audience: enrolled`; W3.2 chunking. The core target went from 48 to 10 on 2026-11-21: the bulk corpus gives the count | data and retrieval | `data/corpus/`, `scripts/generate_bulk_corpus.py`, `data/chunks.jsonl` | Fri 20 |
| 5 | W2.4 Harness, one command; `dates.py` | evaluation and safety / agent and tools | `eval/run_e2e.py`, `src/aic390/dates.py` | Fri 20 · ✓ |
| 6 | **Freeze `week2_cases.jsonl`** before any prompt comparison (R9) | evaluation and safety | ✓ frozen at `5a10169` (42 cases); sha256 in `eval/testsets/README.md`; label notes in `week2_review_notes.jsonl` | Fri 20, 20:00 (done Sat 21, 00:02) |
| 7 | W2.2 Main prompt v1 | agent and tools | `prompts/` | Fri 20, 22:00 · ✓ |
| 8 | W3.5 30 retrieval questions with gold sections, written by someone other than the corpus author; frozen | evaluation and safety, agent and tools | `eval/testsets/retrieval_questions.jsonl` | Sat 21, 12:00 · ✓ frozen |
| 9 | W2.2 Main prompt v2, v3 | agent and tools | `prompts/` | Sat 21, 14:00 · ✓ |
| 10 | W3.3 Hybrid search + reranker; `eval/retrieval.py` | data and retrieval | `src/aic390/rag/`, `eval/retrieval.py` | Sat 21 |
| 11 | W2.5 runs: v1–v3 once each, then the best two repeated; McNemar | evaluation and safety | `results/`, `eval/compare.py` | Sat 21 – Sun 22 · ✓ (repeat runs: 11b) |
| 11b | W2.5 repeat runs not finished: `w25-v2-b` stopped at 17/42 on 2026-11-22 (free-plan rate limit, 200–390 s wait per call), `w25-v3-b` not run. Run both again, same cases and unchanged code (`9decfea`), when the daily limit allows; they are a stability check only, the W2.5 decision comes from the `a` runs (plan row). The partial `v2-b` folder is not committed | evaluation and safety | `results/*_e2e_w25-v2-b_*`, `results/*_e2e_w25-v3-b_*` | Mon 23, before the week-3 runs |
| 12 | W2.6 Judge vs 20 human labels (κ); W2.7 hallucination log ≥ 10; W2.8 three injection attempts | evaluation and safety, agent and tools | `eval/judge.py`, `docs/hallucination_log.md`, `docs/injection_tests.md` | Sun 22, 18:00 · ✓ |
| 12b | `docs/architecture.md`: Mermaid diagram and component table; each owner writes their own rows | all (evaluation and safety assembles) | `docs/architecture.md` | Sun 22, 18:00 · ✓ except the data and retrieval rows |
| 13 | Demo end to end with the temporary search; `reports/week-2.md`, tag `week-2` | agent and tools / evaluation and safety | `app/demo.py`, `reports/week-2.md` | Sun 22 · ✓ report; tag `week-2` pending |
| 14 | W3.7 Two ablations (hybrid vs dense vs BM25; reranker on/off) | data and retrieval | `results/` | Mon 23, 12:00 |
| 15 | W3.4 Cited answers + fixed abstention; 40 cases re-run with RAG; W3.6 faithfulness | agent and tools / evaluation and safety | `src/aic390/agent/answer.py`, `eval/faithfulness.py` | Mon 23, 16:00 |
| 16 | W3.8 Failure analysis (retrieval vs generation, oracle test); product track: 2 interviews | evaluation and safety / all | `reports/week-3.md` | Mon 23, 20:00 |
| 17 | Demo rehearsal with unseen questions, plus architecture questions asked to a random member; measured per-stage latency and tokens added to the component table; tag `week-3` | all | `reports/week-3.md`, `docs/architecture.md` | Mon 23 |
| 18 | Red-team rerun of W2.8 inj-02 with the real model, forcing the look-up path (classified `lookup`), so the access rule itself is what refuses; today it held only because the classifier said `other` (`docs/injection_tests.md`) | agent and tools | `results/`, `docs/injection_tests.md` | week 4 |

**If time runs out, cut in this order.** Nothing on this list is a deliverable: replay-mode polish → extra demo
example buttons → Turkish share of the corpus → core corpus from 48 to 36 documents → second repeat of the W2.5 runs
(report the single run and say so). Not cut: test sets, the ≥ 10,000-chunk scale (instructor's request), the reranker (W3.3 names it; it is also the cheapest
ablation), the second ablation (W3.7 asks for two), judge labels (W2.6, W3.6), the demo.

**Evaluation honesty.** Prompts are developed on the 25 week-1 inputs, which are also in the 40-case set, so the
report gives e2e accuracy separately for the seen 25 and the 15+ new cases.

## Area coverage (R2: every member needs code in ≥ 2 role areas by week 7)

✓ = code committed in that area (scripts, src, tests, data files). Markdown alone is listed as "docs".
"planned" = the code this member owns in weeks 2–3.

| Member | data | agent | eval |
|---|---|---|---|
| Serap Gökçe Yıldız | | planned (sender trust in the pipeline) | ✓ |
| Enes Kemal Köylü | | docs; planned (classifier, prompts, answer, demo) | ✓ |
| Mert Bozma | docs; planned (corpus, chunking, search) | | planned (`eval/retrieval.py`) |

## Experiments

| Date | Hypothesis | Result (value, n, CI) | Decision | Evidence |
|---|---|---|---|---|
| 2026-11-16 | Baseline prompt fails most week-1 inputs (P1–P5) | e2e accuracy 4/25 = 0.16 [0.064, 0.347] at T=0; P1, P3, P4, P5 true, P2 false | Week 2 builds the classifier and main prompt (W2.1, W2.2) | `results/2026-11-16_baseline_openai-gpt-oss-120b/analysis.json` |
| 2026-11-16 | Temperature does not change accuracy (P6) | 4/25 correct at T = 0, 0.7 and 1.2; a second T=0 run changed the answer for 4 of 25 | Run every comparison more than once (W2.5) | `results/2026-11-16_baseline-t0-repeat_openai-gpt-oss-120b/` |
| 2026-11-22 | v1 end to end on the 42 frozen cases (measurement, no comparison) | 39/42 = 0.929 [0.810, 0.975] Wilson; stub search + seed table with expected rows | Extraction is at ceiling (42/42); W2.5 needs a decision rule beyond accuracy | `results/2026-11-22_e2e_v1-stub-seed_openai-gpt-oss-120b/` |
| 2026-11-22 (plan) | **W2.5, main prompt = `extract`.** v2 = v1 plus one block of worked examples (the one building block of Module 2 that v1 lacks); the examples are invented, none comes from a test set (D-009 rule 1). Hypothesis: examples make item_key and the date expression more consistent, so the `deadlines` field fails less often. Everything else (classifier, answer, lookup prompts, code, model, T=0) is the same for v1, v2 and v3: all runs at one commit, where v1 is rerun (the v1 run above was at d29e3f4, before 91299a3 and 631e022 changed the code) | `a` runs at `9decfea`, stub search, seed table: v1 39/42 = 0.929 [0.810, 0.975] Wilson, v2 39/42 [0.810, 0.975], v3 39/42 [0.810, 0.975]. McNemar exact v1-a vs v2-a: b = 1 (w2-14), c = 1 (w1-08), p = 1.0. `deadlines` field errors: v1-a 1 (w1-08), v2-a 0. Tokens (in + out): v1 63,038, v2 71,688, v3 73,162; p50 latency 1.847, 1.813, 1.806 s. Repeat v1-a vs v1-b: 2 correct flips (w1-08, w1-19) and 9/42 answer texts changed, as many flips as between versions. `b` runs: v1-b 39/42; v2-b stopped at 17/42 by the free-plan rate limit, v3-b not run (next actions 11b) | Equal (p = 1.0 ≥ 0.05), so the token rule decides: keep `extract_v1`; v2 not adopted. The `b` runs that exist agree. Decided by: e2e accuracy on the 42 frozen cases with Wilson 95% CI, McNemar exact v1 vs v2, and the count of `deadlines` field errors; same run condition for all three (stub search, `--table seed`), written in `config.json`; two runs per version in the order v1, v2, v3, v1, v2, v3 (labels `w25-<version>-a`, `-b`); McNemar on the `a` runs, the `b` runs show stability, and a different decision between them is reported. v1 is at 42/42 on extraction with the seed table, so with that table no difference in accuracy is expected, and exact McNemar reaches p < 0.05 only with at least 6 discordant cases in one direction (5–0 gives p = 0.0625); the report says both. **Equal means McNemar p ≥ 0.05. If equal, the version with fewer tokens wins (`input_tokens + output_tokens`, n = 42 each), then the lower `latency_p50_s`** (both from `summary.json`). Expected: v1, since v2 and v3 add text; output tokens can still change. Added before any v2 or v3 run | `prompts/extract_v2.md` |
| 2026-11-22 (plan) | **W2.5, v3** = v2 plus clear delimiters around the message text (`<message>` … `</message>`) and a line that everything inside them is data. Hypothesis: no change on the 42 cases (the three adversarial extraction cases already pass); the change is for robustness, so it is also checked on the W2.8 injection attempts | v3-a 39/42 = 0.929 [0.810, 0.975]; McNemar exact v2-a vs v3-a: b = 1 (w1-19), c = 1 (w1-21), p = 1.0; tokens 73,162. W2.8 part: no difference (`25e9afb`, `631e022`) | Equal, the token rule decides: v3 not kept. W2.5 winner: `extract_v1`; the held-out set runs on it. Decided by: the same numbers as v2, McNemar v2 vs v3, and the W2.8 attempts (`docs/injection_tests.md`). Keep v3 only if it is not worse on the 42 cases; if equal, the same token and latency rule decides | `prompts/extract_v3.md` |
| 2026-11-22 (plan) | **W2.6 judge_v1 vs 20 blind human labels.** The judge (`qwen/qwen3.8-27b`, T = 0, D-006) grades `must_include`/`must_not` per criterion; code computes pass. 20 existing answers: the 9 T = 0 baseline answers with judge criteria and 11 v1 e2e answers sampled with seed 0. Labels are committed before the judge runs (enforced in `eval/judge.py`). Hypothesis: judge_v1 agrees with the blind human labels at kappa ≥ 0.6 | kappa 0.802, bootstrap 95% [0.500, 1.000], n = 20; raw agreement 18/20 = 0.900 [0.699, 0.972] Wilson; human labels 11 pass / 9 fail; 0 invalid judge rows. Both disagreements are human pass / judge fail on long hedged baseline answers (w1-09 '0 after 3 days' only implied; w1-19 a conditional 'you'll pass' in a worked example); no judge pass on a human fail. Single human rater | Threshold met on the point estimate (planned rule), so the judge grades `must_include`/`must_not` from week 3 on; the report gives the interval, whose lower end is below 0.6, and the two disagreements. Decided by: Cohen's kappa. kappa ≥ 0.6 → the judge grades `must_include`/`must_not` from week 3 on, the report lists the disagreements; kappa < 0.6 → judge_v2 with one change and 20 new labels, or these fields are graded by a person; the report gives kappa either way. Also reported: confusion matrix, raw agreement with Wilson 95% CI, bootstrap 95% CI of kappa (2,000 resamples, seed 0); an invalid judge output counts as a disagreement | `eval/judge.py`, `prompts/judge_v1.md`, `results/2026-11-22_judge-v1/` |
| 2026-11-22 (plan) | **Held-out `heldout_v1`, one run on the W2.5 winner.** 13 cases written by the evaluation and safety lead only (normal 4, edge 5, unanswerable 2, adversarial 2); only the sha256 is committed until the numbers are reported (D-009 rule 1). Hypothesis: accuracy is lower than on the 42 dev cases. Two causes we cannot separate: the dev set was seen while building (D-009 gap 1), and the held-out set has more edge cases (5 of 13 against 8 of 42) | 6/13 = 0.462 [0.232, 0.709] Wilson, against 39/42 = 0.929 [0.810, 0.975] on the dev set (w25-v1-a): the intervals do not overlap. By type: normal 1/4, edge 2/5, unanswerable 1/2, adversarial 2/2. Failures: h-01, h-02 item_key only (date right; key `hw`, labels `assignment`, `homework`); h-04 key and date `unverified` for "bu ayın sonu"; h-06 cites the calendar but not Article 9; h-08 intent `other`; h-10 look-up ignores "ödev ve proje" and "before December"; h-11 "the night before" set to 24 h before without asking. Run at `0b20cd7`, 24 calls | Hypothesis holds: lower than dev. Normal cases also fell (1/4 against 22/22), so edge-heaviness alone does not explain it; two of seven failures come from our underspecified `item_key` rule, not from the system. Decided by: e2e accuracy with a Wilson 95% interval, by type, next to the dev set; with n = 13 only a large drop is visible. One run, same conditions as the W2.5 winner's runs (stub search, `--table seed`); after it is reported the file is committed and becomes development data, and the next held-out set is `heldout_v2`. Written before the held-out run | `eval/testsets/heldout_v1.jsonl.sha256` |
