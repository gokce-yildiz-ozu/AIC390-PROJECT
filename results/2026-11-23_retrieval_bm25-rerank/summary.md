# Retrieval run `bm25-rerank`

Conditions: bm25, reranker on, top 20 per list, RRF k = 60, None + BAAI/bge-reranker-v2-m3, 11388 chunks, course=None, as_of from the question, device NVIDIA GeForce RTX 5060 Laptop GPU.
Questions: `eval/testsets/retrieval_questions.jsonl` (sha256 `6f7d3b049dab…`, n = 30). Chunks sha256 `3cdd826ef7ec…`. Commit `1bde1de`.

Reportable: yes

| Metric | Value, Wilson 95% |
|---|---|
| hit@1 | 24/30 = 0.800 [0.627, 0.905] |
| hit@3 | 25/30 = 0.833 [0.664, 0.927] |
| hit@5 | 25/30 = 0.833 [0.664, 0.927] |
| hit@10 | 25/30 = 0.833 [0.664, 0.927] |
| MRR (top 10) | 0.817 [0.683, 0.933] bootstrap |
| all@5, multi questions | 2/4 = 0.500 [0.150, 0.850] |
| all@10, multi questions | 2/4 = 0.500 [0.150, 0.850] |

| Group | n | hit@1 | hit@5 | MRR |
|---|---|---|---|---|
| direct | 7 | 0.857 | 1.000 | 0.929 |
| paraphrase | 9 | 0.556 | 0.556 | 0.556 |
| confusable | 7 | 1.000 | 1.000 | 1.000 |
| version | 3 | 1.000 | 1.000 | 1.000 |
| multi | 4 | 0.750 | 0.750 | 0.750 |
| en | 18 | 0.889 | 0.944 | 0.917 |
| tr | 12 | 0.667 | 0.667 | 0.667 |

Search latency per query: median 0.2016 s, p90 0.2557 s (per search call, after one untimed warm-up query; index build not included). Index build 4.76 s.
No gold passage in the top 5 (W3.8 failure table): r02, r04, r23, r25, r28.
