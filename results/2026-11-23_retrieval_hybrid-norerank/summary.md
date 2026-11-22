# Retrieval run `hybrid-norerank`

Conditions: hybrid, reranker off, top 20 per list, RRF k = 60, BAAI/bge-m3 + None, 11388 chunks, course=None, as_of from the question, device NVIDIA GeForce RTX 5060 Laptop GPU.
Questions: `eval/testsets/retrieval_questions.jsonl` (sha256 `6f7d3b049dab…`, n = 30). Chunks sha256 `3cdd826ef7ec…`. Commit `1bde1de`.

Reportable: yes

| Metric | Value, Wilson 95% |
|---|---|
| hit@1 | 25/30 = 0.833 [0.664, 0.927] |
| hit@3 | 28/30 = 0.933 [0.787, 0.982] |
| hit@5 | 29/30 = 0.967 [0.833, 0.994] |
| hit@10 | 29/30 = 0.967 [0.833, 0.994] |
| MRR (top 10) | 0.879 [0.774, 0.973] bootstrap |
| all@5, multi questions | 2/4 = 0.500 [0.150, 0.850] |
| all@10, multi questions | 2/4 = 0.500 [0.150, 0.850] |

| Group | n | hit@1 | hit@5 | MRR |
|---|---|---|---|---|
| direct | 7 | 1.000 | 1.000 | 1.000 |
| paraphrase | 9 | 0.444 | 0.889 | 0.596 |
| confusable | 7 | 1.000 | 1.000 | 1.000 |
| version | 3 | 1.000 | 1.000 | 1.000 |
| multi | 4 | 1.000 | 1.000 | 1.000 |
| en | 18 | 0.944 | 1.000 | 0.963 |
| tr | 12 | 0.667 | 0.917 | 0.753 |

Search latency per query: median 0.0066 s, p90 0.0122 s (per search call, after one untimed warm-up query; index build not included). Index build 5.51 s.
No gold passage in the top 5 (W3.8 failure table): r02.
