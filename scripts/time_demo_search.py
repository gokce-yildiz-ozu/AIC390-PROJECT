"""How long the demo's hybrid search takes on this computer: index load, then each query. No model API call.

    python scripts/embed_corpus.py        # first, so the embedding cache is full
    python scripts/time_demo_search.py    # run in a fresh process: load time includes reading both models

Queries are the demo's own invented rule questions (aic390.demo.EXAMPLES) plus a few more invented ones; none is a
test-set question. Writes results/<date>_demo-search-timing_<device>/summary.json.
"""

import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPEATS = 3
QUERIES = [
    ("How is late work graded?", "CS-301"),
    ("What happens if I miss an exam because I am ill?", None),
    ("Dersten nasıl çekilebilirim?", None),
    ("When do lectures take place?", "MATH-212"),
    ("Is attendance required?", "CS-310"),
]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def main() -> int:
    import torch

    from aic390 import demo
    from aic390.rag import search as rag

    device = "cuda" if torch.cuda.is_available() else "cpu"
    start = time.perf_counter()
    search = demo.make_search("hybrid")  # loads both models, reads the cached vectors, runs one warm-up query
    load_s = time.perf_counter() - start

    queries = QUERIES + [(e["case"]["text"], e["case"]["course"]) for e in demo.EXAMPLES if "rule" in e["id"]]
    latencies = []
    for query, course in queries:
        for _ in range(REPEATS):
            # An empty query cache each time: a question asked in the demo is new, so its embedding is computed.
            with tempfile.TemporaryDirectory() as empty:
                rag._default.embedder.cache_dir = Path(empty)
                start = time.perf_counter()
                search(query, course=course, as_of="2026-11-19T10:00:00+03:00")
                latencies.append(time.perf_counter() - start)
    latencies.sort()
    summary = {
        "script": "scripts/time_demo_search.py",
        "commit": git("rev-parse", "--short", "HEAD"),
        "uncommitted_changes": bool(git("status", "--porcelain", "src", "scripts", "data")),
        "device": device,
        "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
        "cpu": platform.processor(),
        "torch_threads": torch.get_num_threads(),
        "embedding_model": rag.EMBEDDING_MODEL,
        "reranker_model": rag.RERANKER_MODEL,
        "n_chunks": demo.n_chunks("hybrid"),
        "load_s": round(load_s, 2),
        "n_queries": len(latencies),
        "query_latency_s": {
            "p50": round(statistics.median(latencies), 3),
            "min": round(latencies[0], 3),
            "max": round(latencies[-1], 3),
        },
    }
    out = ROOT / "results" / f"{date.today().isoformat()}_demo-search-timing_{device}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
