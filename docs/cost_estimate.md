# Cost estimate (W1.6)

Owner: agent and tools lead. Every number below comes from the week-1 baseline run and is reproduced by:

```powershell
python scripts/cost_breakdown.py results/2026-11-16_baseline_openai-gpt-oss-120b
```

Source data: `results/2026-11-16_baseline_openai-gpt-oss-120b/outputs.jsonl` (75 calls: 25 inputs × temperatures
0, 0.7 and 1.2). Result file: `results/2026-11-16_baseline_openai-gpt-oss-120b/cost_breakdown.json`.

## Result

**$0.289 per 1,000 requests** (mean $0.000289 per request), n = 75, model `openai/gpt-oss-120b` on Groq, prompt
`baseline_v1`. Our actual spend this week is **$0**, because we run on Groq's free plan (D-006).

## Formula

```
cost per request = (input_tokens × input_price + output_tokens × output_price) / 1,000,000
$ per 1,000 requests = 1,000 × mean(cost per request)
```

| Price | USD per million tokens | Source |
|---|---|---|
| Input | 0.15 | Groq model page, checked 2026-11-16 (`config/prices.json`) |
| Output | 0.60 | same |

## Assumptions

1. **List price, not our price.** We pay nothing on the free plan; we cost every call at Groq's paid list price for
   the same model, so the number is what a paying deployment would pay.
2. **Same model only.** The price is applied only to tokens produced by `gpt-oss-120b`. Another model has a
   different tokenizer and different answer lengths, so its cost has to be measured, not converted.
3. **Reasoning tokens are output tokens.** The API counts them inside `completion_tokens`, and the price page lists
   no separate price for them.
4. **No cached-input discount.** Groq lists $0.075 for cached input; we ignore it, so the estimate is slightly high
   if the system prompt is cached.
5. **One request = one model call.** Week 1 has no retrieval, tools or agent loop. From week 4 a task makes several
   calls, so cost per task will be higher than this number.
6. **Token counts are the provider's.** They come from the `usage` field of each API response, recorded by
   `src/aic390/llm.py`, not from our own token counting.

## Tokens per request

| | n | Mean input | Mean output | of which reasoning | p50 total | p95 total | $ per 1,000 requests |
|---|---|---|---|---|---|---|---|
| All calls | 75 | 222 | 426 | 116 | 518 | 1,353 | 0.289 |
| Email | 21 | 248 | 177 | 138 | 429 | 508 | 0.143 |
| LMS post | 12 | 249 | 275 | 182 | 541 | 627 | 0.202 |
| Chat question | 42 | 202 | 593 | 87 | 720 | 1,454 | 0.386 |

By temperature: $0.303 (T = 0), $0.274 (T = 0.7) and $0.290 (T = 1.2) per 1,000 requests, n = 25 each. We did not
test whether these differ; with 25 calls each we treat them as the same.

## What the numbers show

- **Output drives the cost.** Output tokens cost 4× input tokens and are about twice as many, so they make up about
  88 % of the cost. Shorter answers are the main way to cut cost.
- **Hidden reasoning is a quarter of the cost.** Reasoning tokens are 24 % of the total cost, and more than half of
  it for emails (58 %) and LMS posts (54 %). Counting only the visible answer would underestimate the cost.
- **Questions cost more than messages.** A chat question costs 2.7× an email ($0.386 vs $0.143), because the
  model writes long free-form answers. This is input for the week-2 main prompt (W2.2): ask for short answers.
- **Fixed overhead.** A smoke test that only answered "OK" used 75 input and 52 output tokens (D-006), so even a
  trivial request is not free.
