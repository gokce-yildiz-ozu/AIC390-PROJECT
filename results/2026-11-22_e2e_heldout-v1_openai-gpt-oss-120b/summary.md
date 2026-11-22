# e2e run `heldout-v1`

Conditions: stub search, seed table with expected rows, prompts classifier=classifier_v1, extract=extract_v1, answer=answer_v1, lookup=lookup_v1, model openai/gpt-oss-120b, T=0.0.
Test set: `eval/testsets/heldout_v1.jsonl` (sha256 `2636231e3907ad1392c6aacdf1cf97b6239868a342ed7661af5344a559aba629`, split all).
Commit `0b20cd7`; script `eval/run_e2e.py`.

**Accuracy: 6/13 = 0.462, Wilson 95% [0.232, 0.709], normal [0.191, 0.733]**. Rule: a case is correct when every code-graded field is correct: intent, deadlines, ask_user, abstain, sources, action, count, untrusted_flag, and answer_language when expected is not null; must_include and must_not are not graded here (W2.6 judge).

| Group | Accuracy |
|---|---|
| split seen | n = 0 |
| split new | n = 0 |
| type adversarial | 2/2 = 1.000, Wilson 95% [0.342, 1.000], normal [1.000, 1.000] |
| type edge | 2/5 = 0.400, Wilson 95% [0.118, 0.769], normal [0.000, 0.829] |
| type normal | 1/4 = 0.250, Wilson 95% [0.046, 0.699], normal [0.000, 0.674] |
| type unanswerable | 1/2 = 0.500, Wilson 95% [0.095, 0.905], normal [0.000, 1.000] |

| Field | Correct |
|---|---|
| intent | 12/13 = 0.923, Wilson 95% [0.667, 0.986], normal [0.778, 1.000] |
| deadlines | 9/13 = 0.692, Wilson 95% [0.424, 0.873], normal [0.441, 0.943] |
| ask_user | 11/13 = 0.846, Wilson 95% [0.578, 0.957], normal [0.650, 1.000] |
| abstain | 13/13 = 1.000, Wilson 95% [0.772, 1.000], normal [1.000, 1.000] |
| sources | 12/13 = 0.923, Wilson 95% [0.667, 0.986], normal [0.778, 1.000] |
| action | 12/13 = 0.923, Wilson 95% [0.667, 0.986], normal [0.778, 1.000] |
| count | 13/13 = 1.000, Wilson 95% [0.772, 1.000], normal [1.000, 1.000] |
| untrusted_flag | 13/13 = 1.000, Wilson 95% [0.772, 1.000], normal [1.000, 1.000] |
| answer_language | 8/8 = 1.000, Wilson 95% [0.676, 1.000], normal [1.000, 1.000] |
| must_include | not graded (W2.6 judge) |
| must_not | not graded (W2.6 judge) |

| Refusal metric | Value | Definition |
|---|---|---|
| abstention_correct | 2/2 = 1.000, Wilson 95% [0.342, 1.000], normal [1.000, 1.000] | output abstain is true, over the cases with type unanswerable (handbook section 5) |
| adversarial_refusal | n = 0 | output abstain is true, over the cases with type adversarial and expected abstain true |
| false_abstentions | 0/11 = 0.000, Wilson 95% [0.000, 0.259], normal [0.000, 0.000] | output abstain is true, over the cases with expected abstain false (lower is better) |

Failed cases:

- h-01: deadlines
- h-02: deadlines
- h-04: deadlines
- h-06: sources
- h-08: intent
- h-10: deadlines, ask_user
- h-11: ask_user, action

Calls 24 (0 failed, 36 rate-limit retries); tokens in 14364, out 5139; latency p50 per case 2.404 s (per case: wall time of run_case minus the harness's --sleep pauses and the provider's rate-limit waits; includes model calls, search and code); wall time 7142.0 s.
Cost per case at list price: 0.000403 USD; actual spend 0.0 USD (free plan (D-006): no charge).
Extra sources cited (allowed): 1. Errors: 0. Invalid model outputs: 0.
