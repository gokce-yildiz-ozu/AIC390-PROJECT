# Course requirements: our working checklist

Condensed from the course's *Applied project handbook* (instructor: Hüseyin Ulusoy) so the whole team has every
deliverable's requirements in one place, next to the code. The handbook is authoritative; if this file and the
handbook disagree, the handbook wins and this file gets fixed.

## Architecture we must build (same for every team, only the domain differs)

| # | Layer | Must do |
|---|---|---|
| 1 | Understand | Classifier → JSON (intent, entities, urgency), schema-validated, temperature 0, retry |
| 2 | Answer | RAG over our docs, numbered citations, fixed "not in the documents" response |
| 3 | Look up | Query tool over structured data (counts and current values come from here, never from the model) |
| 4 | Act | One write action behind a confirmation step, sandbox only |
| 5 | Connect | All tools exposed as an MCP server, usable from a standard MCP host; state the spec revision |
| 6 | Orchestrate | Agent loop with step, token and time limits, repeated-call detection, clear stop message |
| 7 | Measure | One-command harness that rewrites `eval/scoreboard.json` |

## Weekly deliverables

A deliverable without an evidence link counts as not done.

**Week 1 (problem and baseline)**
- W1.1 Team agreement: roles, meeting times, decision rule, non-delivery rule, post-course ownership.
- W1.2 Use case brief: first customer, persona, 5 user stories, in/out of scope.
- W1.3 25 realistic inputs, each labelled with the ingredients it tests (question, look-up, action,
  unanswerable, multi-step, …).
- W1.4 Data inventory: documents, DB tables/columns, sketch of the action API, untrusted-input sources.
- W1.5 Baseline: one prompt on all 25 inputs at temperatures 0, 0.7 and 1.2, with what changed and why.
- W1.6 Cost estimate: tokens per request and $ per 1,000 requests, formula and assumptions.
- W1.7 At least 5 predicted failures, each tied to a Module 1 concept (tokens, knowledge cutoff, statelessness…).
- W1.8 Repo with README, tagged `week-1`.

**Week 2 (prompts and evaluation harness)**
- W2.1 Classifier with schema-following JSON, temp 0, validation + retry.
- W2.2 Main prompt from the six building blocks, stored as a versioned template.
- W2.3 Test set ≥ 40 cases with expected outputs, tagged by type: ≥5 unanswerable, ≥5 adversarial, ≥5 edge.
- W2.4 Harness: one command runs every case and writes the scoreboard file.
- W2.5 Three prompt versions: accuracy with 95% intervals + McNemar test between the best two.
- W2.6 LLM judge for open answers, validated on 20 human labels with Cohen's κ.
- W2.7 Hallucination log ≥ 10 examples, typed (fabricated fact / unfaithful / reasoning error).
- W2.8 3 direct prompt-injection attempts on our own system and what happened.

**Week 3 (RAG)** — product track: talk to ≥2 potential customers, summarize.
- W3.1 Corpus ≥ 30 docs, cleaned, metadata: source, date/version, who may see it.
- W3.2 Chunking choice with chunk count and justification.
- W3.3 Hybrid search (BM25 + embeddings, reciprocal rank fusion) + reranker.
- W3.4 Numbered citations; fixed response when the docs don't contain the answer.
- W3.5 Retrieval test set ≥ 30 questions with gold passages: hit@1/3/5/10 and MRR.
- W3.6 Claim-level faithfulness; judge checked against human labels.
- W3.7 Two ablations, one change each (e.g. chunk size, hybrid vs dense, reranker on/off).
- W3.8 Failure analysis labelling each failure retrieval vs generation.

**Week 4 (tools and agent loop)** — each student submits peer assessment #1.
- W4.1 ≥3 tools (doc search, data query, one write action): clear descriptions, tight schemas, concise results,
  helpful errors.
- W4.2 Agent loop with step/token/time limits, repeated-call detection, clear limit message.
- W4.3 Context management: trimming or compaction of old tool results.
- W4.4 ≥10 multi-step tasks with expected outcomes and saved traces.
- W4.5 Cost per task, measured and compared with Module 4's context-growth formula.
- W4.6 Design note: single call vs workflow vs agent for each feature, and why.
- W4.7 Write action works only against our fake API.

**Week 5 (MCP and security)** — product track: pricing hypothesis vs measured cost per task.
- W5.1 MCP server exposing our tools; state the spec revision the SDK implements.
- W5.2 Demo inside a standard MCP host.
- W5.3 Lethal-trifecta analysis and a risk tier per tool.
- W5.4 Confirmation step for every write action, showing exactly what will happen.
- W5.5 Red-team attack: ≥5 attacks on our assigned team (via documents, data, untrusted input), reported with
  reproduction steps to them and the instructor.
- W5.6 Red-team defense: success rate of their attacks on us, before and after fixes.

**Week 6 (agent evaluation and hardening)**
- W6.1 Sandbox with fake tools and resettable state.
- W6.2 ≥20 agent tasks, each with expected final state, forbidden actions, budget.
- W6.3 Each task run 5×: success rate, pass^5, steps, cost, latency.
- W6.4 Top 3 failures fixed from transcript review, before/after.
- W6.5 **Hidden-test run command:** one command reads tasks from a file and writes results to a file.
- W6.6 Regression check: every earlier test still passes, or the change is explained.

**Week 7 (final)**
- F1 Live demo on instructor-chosen tasks. F2 Final report ≤ 4,000 words. F3 One-page business case.
- F4 Repo tagged `final`, README sets up the system in ≤ 10 commands. F5 Peer assessment #2.

## Scoreboard keys (`eval/scoreboard.json`)

`week`, `test_set_size`, `e2e_accuracy`, `abstention_correct`, `unsupported_claims`, `hit_at_5`, `mrr`,
`task_success`, `pass_k`, `injection_success`, `cost_per_task_usd`, `latency_p50_s`, `spend_week_usd`,
`spend_total_usd`. Accuracy-type entries are `{value, ci95, n, script}`. Unmeasured = `null`.

## Weekly report (`reports/week-N.md`)

Template: `docs/weekly_report_template.md`. Sections in fixed order: 0 Header, 1 Summary (≤100 words),
2 Deliverables table, 3 Scoreboard JSON, 4 Experiments (hypothesis, change, result with n and uncertainty,
decision), 5 Top-3 failures (input, what happened, root-cause category, fix), 6 Response to last week's feedback,
7 Product track, 8 Contributions (per member: work, commits/files, hours), 9 AI tools used, 10 Next week (top 3,
each with metric and target). ≤ 1,500 words excluding tables. Root-cause categories: prompt, retrieval,
generation, tool design, loop, data, security, evaluation.

## How we're graded (what moves the grade)

| Component | Weight | Lever |
|---|---|---|
| Weekly milestones W1–W6 | 36% | Rubric A–E, each 0–4: Completeness, Evidence, Failure analysis, Engineering quality, Progress. 3 = solid, 4 = goes beyond with evidence (rigorous experiment, insight others can learn from) |
| Final (demo, report, business case) | 24% | Live demo on unseen tasks |
| Hidden test set | 10% | 10 unseen cases × 3 runs via our W6.5 command. Overfitting to our own test set hurts here |
| Red-team exchange | 10% | Defense: 5 × (1 − share of their attacks still succeeding). Attack: variety, clarity, rules |
| Individual | 20% | Commit evidence (8%), answering any question in presentations (6%), peer rating (6%) |

All 3s ≈ 75% of milestone points = B. An A needs 4s, strong hidden-test and defense results, and clear individual
contribution. Penalties: late report −25% (≤24 h) or 0; an unreproducible number = deliverable not done;
fabrication or grader-targeted text = 0 and misconduct; real action outside the sandbox = 0 on criterion D.

## Weekly presentation (8 min + 5 min Q&A, presenter rotates)

What we built (2) · scoreboard vs last week, same slide layout every week (2) · what failed and why (2) ·
next week's top 3 and the number each should move (1). Expect: *What did you measure and how sure are you? What
failed and do you know why? Is next week's plan the change that matters most?* Anyone can be asked about any part.
