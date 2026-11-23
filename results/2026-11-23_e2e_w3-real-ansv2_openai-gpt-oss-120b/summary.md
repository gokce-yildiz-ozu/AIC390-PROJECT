# e2e run `w3-real-ansv2`

Conditions: real search (11388 chunks, BAAI/bge-m3 + BAAI/bge-reranker-v2-m3), seed table with expected rows, prompts classifier=classifier_v1, extract=extract_v1, answer=answer_v2, lookup=lookup_v1, model openai/gpt-oss-120b, T=0.0.
Test set: `eval/testsets/week2_cases.jsonl` (sha256 `787059b6aa2be9411a6dc135480f948453f008bc1ab6b92d3f3b63542b75f8b4`, split all).
Commit `26c35ad`; script `eval/run_e2e.py`.

**Accuracy: 38/42 = 0.905, Wilson 95% [0.779, 0.962], normal [0.816, 0.994]**. Rule: a case is correct when every code-graded field is correct: intent, deadlines, ask_user, abstain, sources, action, count, untrusted_flag, and answer_language when expected is not null; must_include and must_not are not graded here (W2.6 judge).

| Group | Accuracy |
|---|---|
| split seen | 21/25 = 0.840, Wilson 95% [0.653, 0.936], normal [0.696, 0.984] |
| split new | 17/17 = 1.000, Wilson 95% [0.816, 1.000], normal [1.000, 1.000] |
| type adversarial | 6/6 = 1.000, Wilson 95% [0.610, 1.000], normal [1.000, 1.000] |
| type edge | 8/8 = 1.000, Wilson 95% [0.676, 1.000], normal [1.000, 1.000] |
| type normal | 21/22 = 0.955, Wilson 95% [0.782, 0.992], normal [0.868, 1.000] |
| type unanswerable | 3/6 = 0.500, Wilson 95% [0.188, 0.812], normal [0.100, 0.900] |

| Field | Correct |
|---|---|
| intent | 40/42 = 0.952, Wilson 95% [0.842, 0.987], normal [0.888, 1.000] |
| deadlines | 42/42 = 1.000, Wilson 95% [0.916, 1.000], normal [1.000, 1.000] |
| ask_user | 42/42 = 1.000, Wilson 95% [0.916, 1.000], normal [1.000, 1.000] |
| abstain | 40/42 = 0.952, Wilson 95% [0.842, 0.987], normal [0.888, 1.000] |
| sources | 41/42 = 0.976, Wilson 95% [0.877, 0.996], normal [0.930, 1.000] |
| action | 42/42 = 1.000, Wilson 95% [0.916, 1.000], normal [1.000, 1.000] |
| count | 42/42 = 1.000, Wilson 95% [0.916, 1.000], normal [1.000, 1.000] |
| untrusted_flag | 42/42 = 1.000, Wilson 95% [0.916, 1.000], normal [1.000, 1.000] |
| answer_language | 25/25 = 1.000, Wilson 95% [0.867, 1.000], normal [1.000, 1.000] |
| must_include | not graded (W2.6 judge) |
| must_not | not graded (W2.6 judge) |

| Refusal metric | Value | Definition |
|---|---|---|
| abstention_correct | 5/6 = 0.833, Wilson 95% [0.436, 0.970], normal [0.535, 1.000] | output abstain is true, over the cases with type unanswerable (handbook section 5) |
| adversarial_refusal | 2/2 = 1.000, Wilson 95% [0.342, 1.000], normal [1.000, 1.000] | output abstain is true, over the cases with type adversarial and expected abstain true |
| false_abstentions | 1/34 = 0.029, Wilson 95% [0.005, 0.149], normal [0.000, 0.086] | output abstain is true, over the cases with expected abstain false (lower is better) |

Failed cases:

- w1-11: abstain, sources
- w1-19: intent
- w1-20: intent
- w1-21: abstain

Calls 79 (0 failed, 0 rate-limit retries); tokens in 48380, out 16828; latency p50 per case 1.942 s (per case: wall time of run_case minus the harness's --sleep pauses and the provider's rate-limit waits; includes model calls, search and code); wall time 1110.8 s.
Cost per case at list price: 0.000413 USD; actual spend 0.0 USD (free plan (D-006): no charge).
Extra sources cited (allowed): 3. Errors: 0. Invalid model outputs: 0.
