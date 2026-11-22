"""Embed data/chunks.jsonl with bge-m3 into the disk cache (.cache/embeddings, not committed) and time it.

    python scripts/embed_corpus.py --limit 200      # time a sample first
    python scripts/embed_corpus.py                  # every chunk; an interrupted run keeps what it finished

Prints one JSON line: chunks embedded now, seconds, ms per chunk, device, model and revision. Cached chunks are
skipped, so a second run is fast; eval/retrieval.py then builds its index from the cache.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))


def main() -> int:
    from retrieval import device_name, model_revision

    from aic390.rag.search import DEFAULT_CHUNKS, EMBEDDING_MODEL, default_embedder, load_chunks

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=0, help="only the first N chunks")
    ap.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    args = ap.parse_args()

    texts = [c["index_text"] for c in load_chunks(args.chunks)]
    if args.limit:
        texts = texts[: args.limit]
    start = time.perf_counter()
    embedder = default_embedder()
    load_s = time.perf_counter() - start
    todo = embedder.missing(texts)
    start = time.perf_counter()
    vectors = embedder.encode(texts)
    seconds = time.perf_counter() - start
    print(
        json.dumps(
            {
                "chunks": len(texts),
                "embedded_now": todo,
                "already_cached": len(texts) - todo,
                "seconds": round(seconds, 1),
                "ms_per_new_chunk": round(1000 * seconds / todo, 1) if todo else None,
                "model_load_s": round(load_s, 1),
                "dimensions": int(vectors.shape[1]),
                "device": device_name(),
                "model": EMBEDDING_MODEL,
                "revision": model_revision(EMBEDDING_MODEL),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
