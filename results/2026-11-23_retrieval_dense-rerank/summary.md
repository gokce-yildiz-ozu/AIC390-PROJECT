# Retrieval run `dense-rerank`

Conditions: dense, reranker on, top 20 per list, RRF k = 60, BAAI/bge-m3 + BAAI/bge-reranker-v2-m3, 11388 chunks, course=None, as_of from the question, device NVIDIA GeForce RTX 5060 Laptop GPU.
Questions: `eval/testsets/retrieval_questions.jsonl` (sha256 `6f7d3b049dab…`, n = 30). Chunks sha256 `3cdd826ef7ec…`. Commit `1bde1de`.

Reportable: yes

| Metric | Value, Wilson 95% |
|---|---|
| hit@1 | 27/30 = 0.900 [0.744, 0.965] |
| hit@3 | 28/30 = 0.933 [0.787, 0.982] |
| hit@5 | 28/30 = 0.933 [0.787, 0.982] |
| hit@10 | 28/30 = 0.933 [0.787, 0.982] |
| MRR (top 10) | 0.917 [0.817, 1.000] bootstrap |
| all@5, multi questions | 2/4 = 0.500 [0.150, 0.850] |
| all@10, multi questions | 2/4 = 0.500 [0.150, 0.850] |

| Group | n | hit@1 | hit@5 | MRR |
|---|---|---|---|---|
| direct | 7 | 0.857 | 1.000 | 0.929 |
| paraphrase | 9 | 0.778 | 0.778 | 0.778 |
| confusable | 7 | 1.000 | 1.000 | 1.000 |
| version | 3 | 1.000 | 1.000 | 1.000 |
| multi | 4 | 1.000 | 1.000 | 1.000 |
| en | 18 | 0.944 | 1.000 | 0.972 |
| tr | 12 | 0.833 | 0.833 | 0.833 |

Search latency per query: median 0.2012 s, p90 0.2472 s (per search call, after one untimed warm-up query; index build not included). Index build 9.11 s.
No gold passage in the top 5 (W3.8 failure table): r02, r09.
