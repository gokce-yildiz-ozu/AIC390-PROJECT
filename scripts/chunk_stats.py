"""W3.2: words per chunk in data/chunks.jsonl (count, median, p90, max), overall and by corpus layer.

    python scripts/chunk_stats.py      # writes results/<date>_chunk-stats/summary.json

Counts the words of each chunk's own text (not the title and section prefix that is added for indexing).
"""

import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))


def percentile(sorted_values: list[int], q: float) -> float:
    """Linear interpolation between the closest ranks (numpy's default method)."""
    pos = (len(sorted_values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def stats(words: list[int]) -> dict:
    s = sorted(words)
    return {
        "chunks": len(s),
        "min": s[0],
        "median": statistics.median(s),
        "p90": round(percentile(s, 0.9), 1),
        "max": s[-1],
    }


def main() -> int:
    from aic390.rag.chunking import DEFAULT_MAX_WORDS
    from aic390.rag.search import DEFAULT_CHUNKS, load_chunks

    chunks = load_chunks(DEFAULT_CHUNKS)
    core = {p.stem for p in (ROOT / "data" / "corpus").glob("*.md")}
    words = [len(c["text"].split()) for c in chunks]
    summary = {
        "chunks_path": "data/chunks.jsonl",
        "chunks_sha256": __import__("run_e2e").lf_sha256(DEFAULT_CHUNKS),
        "max_words": DEFAULT_MAX_WORDS,
        "unit": "words of the chunk text, split on whitespace",
        "all": stats(words),
        "core": stats([w for w, c in zip(words, chunks, strict=True) if c["doc_id"] in core]),
        "bulk": stats([w for w, c in zip(words, chunks, strict=True) if c["doc_id"] not in core]),
        "split_sections": sum(1 for c in chunks if not c["chunk_id"].endswith("::0")),
    }
    out = ROOT / "results" / f"{date.today().isoformat()}_chunk-stats"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out.relative_to(ROOT).as_posix()}/summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
