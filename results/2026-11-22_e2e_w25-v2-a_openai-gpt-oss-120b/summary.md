# e2e run `w25-v2-a`

Conditions: stub search, seed table with expected rows, prompts classifier=classifier_v1, extract=extract_v2, answer=answer_v1, lookup=lookup_v1, model openai/gpt-oss-120b, T=0.0.
Test set: `eval/testsets/week2_cases.jsonl` (sha256 `787059b6aa2be9411a6dc135480f948453f008bc1ab6b92d3f3b63542b75f8b4`, split all).
Commit `9decfea`; script `eval/run_e2e.py`.

**Accuracy: 39/42 = 0.929, Wilson 95% [0.810, 0.975], normal [0.851, 1.000]**. Rule: a case is correct when every code-graded field is correct: intent, deadlines, ask_user, abstain, sources, action, count, untrusted_flag, and answer_language when expected is not null; must_include and must_not are not graded here (W2.6 judge).

| Group | Accuracy |
|---|---|
| split seen | 23/25 = 0.920, Wilson 95% [0.750, 0.978], normal [0.814, 1.000] |
| split new | 16/17 = 0.941, Wilson 95% [0.730, 0.990], normal [0.829, 1.000] |
| type adversarial | 5/6 = 0.833, Wilson 95% [0.436, 0.970], normal [0.535, 1.000] |
| type edge | 8/8 = 1.000, Wilson 95% [0.676, 1.000], normal [1.000, 1.000] |
| type normal | 22/22 = 1.000, Wilson 95% [0.851, 1.000], normal [1.000, 1.000] |
| type unanswerable | 4/6 = 0.667, Wilson 95% [0.300, 0.903], normal [0.289, 1.000] |

| Field | Correct |
|---|---|
| intent | 40/42 = 0.952, Wilson 95% [0.842, 0.987], normal [0.888, 1.000] |
| deadlines | 42/42 = 1.000, Wilson 95% [0.916, 1.000], normal [1.000, 1.000] |
| ask_user | 42/42 = 1.000, Wilson 95% [0.916, 1.000], normal [1.000, 1.000] |
| abstain | 41/42 = 0.976, Wilson 95% [0.877, 0.996], normal [0.930, 1.000] |
| sources | 42/42 = 1.000, Wilson 95% [0.916, 1.000], normal [1.000, 1.000] |
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
| false_abstentions | 0/34 = 0.000, Wilson 95% [0.000, 0.102], normal [0.000, 0.000] | output abstain is true, over the cases with expected abstain false (lower is better) |

Failed cases:

- w1-20: intent
- w1-21: abstain
- w2-14: intent

Calls 78 (0 failed, 0 rate-limit retries); tokens in 55002, out 16686; latency p50 per case 1.813 s (per case: wall time of run_case minus the harness's --sleep pauses and the provider's rate-limit waits; includes model calls, search and code); wall time 1077.7 s.
Cost per case at list price: 0.000435 USD; actual spend 0.0 USD (free plan (D-006): no charge).
Extra sources cited (allowed): 3. Errors: 0. Invalid model outputs: 0.
