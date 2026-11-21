"""W3.2: chunk the corpus into data/chunks.jsonl and print the counts the report needs.

Offline: reads Markdown files, no model and no API call.

    python scripts/build_chunks.py
    python scripts/build_chunks.py --max-words 100 --out results/chunks_100.jsonl   # chunk-size ablation
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aic390.rag.chunking import DEFAULT_MAX_WORDS, build_chunks, write_jsonl  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", nargs="+", type=Path, default=[ROOT / "data/corpus", ROOT / "data/corpus_bulk"])
    parser.add_argument("--out", type=Path, default=ROOT / "data/chunks.jsonl")
    parser.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS)
    args = parser.parse_args()

    chunks = build_chunks(args.corpus, args.max_words)
    write_jsonl(chunks, args.out)

    words = sorted(len(c["text"].split()) for c in chunks)
    summary = {
        "documents": len({c["doc_id"] for c in chunks}),
        "chunks": len(chunks),
        "max_words": args.max_words,
        "words_per_chunk": {"min": words[0], "median": words[len(words) // 2], "max": words[-1]} if words else None,
        "chunks_by_doc_type": dict(sorted(Counter(c["doc_type"] for c in chunks).items())),
        "chunks_by_language": dict(sorted(Counter(c["language"] for c in chunks).items())),
        "out": str(args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
