**NOT FOR REPORTING**: subset of the test set (--ids / --limit)

# e2e run `w3-real-ansv1`

Conditions: real search (11388 chunks, BAAI/bge-m3 + BAAI/bge-reranker-v2-m3), seed table with expected rows, prompts classifier=classifier_v1, extract=extract_v1, answer=answer_v1, lookup=lookup_v1, model openai/gpt-oss-120b, T=0.0.
Test set: `eval/testsets/week2_cases.jsonl` (sha256 `787059b6aa2be9411a6dc135480f948453f008bc1ab6b92d3f3b63542b75f8b4`, split all).
Commit `8fe2a9d`; script `eval/run_e2e.py`.

**Accuracy: 17/19 = 0.895, Wilson 95% [0.686, 0.971], normal [0.757, 1.000]**. Rule: a case is correct when every code-graded field is correct: intent, deadlines, ask_user, abstain, sources, action, count, untrusted_flag, and answer_language when expected is not null; must_include and must_not are not graded here (W2.6 judge).

| Group | Accuracy |
|---|---|
| split seen | 10/12 = 0.833, Wilson 95% [0.552, 0.953], normal [0.623, 1.000] |
| split new | 7/7 = 1.000, Wilson 95% [0.646, 1.000], normal [1.000, 1.000] |
| type adversarial | 1/1 = 1.000, Wilson 95% [0.206, 1.000], normal [1.000, 1.000] |
| type edge | 2/2 = 1.000, Wilson 95% [0.342, 1.000], normal [1.000, 1.000] |
| type normal | 9/10 = 0.900, Wilson 95% [0.596, 0.982], normal [0.714, 1.000] |
| type unanswerable | 5/6 = 0.833, Wilson 95% [0.436, 0.970], normal [0.535, 1.000] |

| Field | Correct |
|---|---|
| intent | 18/19 = 0.947, Wilson 95% [0.754, 0.991], normal [0.847, 1.000] |
| deadlines | 19/19 = 1.000, Wilson 95% [0.832, 1.000], normal [1.000, 1.000] |
| ask_user | 19/19 = 1.000, Wilson 95% [0.832, 1.000], normal [1.000, 1.000] |
| abstain | 18/19 = 0.947, Wilson 95% [0.754, 0.991], normal [0.847, 1.000] |
| sources | 18/19 = 0.947, Wilson 95% [0.754, 0.991], normal [0.847, 1.000] |
| action | 19/19 = 1.000, Wilson 95% [0.832, 1.000], normal [1.000, 1.000] |
| count | 19/19 = 1.000, Wilson 95% [0.832, 1.000], normal [1.000, 1.000] |
| untrusted_flag | 19/19 = 1.000, Wilson 95% [0.832, 1.000], normal [1.000, 1.000] |
| answer_language | 14/14 = 1.000, Wilson 95% [0.785, 1.000], normal [1.000, 1.000] |
| must_include | not graded (W2.6 judge) |
| must_not | not graded (W2.6 judge) |

| Refusal metric | Value | Definition |
|---|---|---|
| abstention_correct | 6/6 = 1.000, Wilson 95% [0.610, 1.000], normal [1.000, 1.000] | output abstain is true, over the cases with type unanswerable (handbook section 5) |
| adversarial_refusal | n = 0 | output abstain is true, over the cases with type adversarial and expected abstain true |
| false_abstentions | 1/13 = 0.077, Wilson 95% [0.014, 0.333], normal [0.000, 0.222] | output abstain is true, over the cases with expected abstain false (lower is better) |

Failed cases:

- w1-11: abstain, sources
- w1-20: intent

Calls 38 (0 failed, 0 rate-limit retries); tokens in 23098, out 8515; latency p50 per case 2.057 s (per case: wall time of run_case minus the harness's --sleep pauses and the provider's rate-limit waits; includes model calls, search and code); wall time 524.3 s.
Cost per case at list price: 0.000451 USD; actual spend 0.0 USD (free plan (D-006): no charge).
Extra sources cited (allowed): 1. Errors: 0. Invalid model outputs: 0.
