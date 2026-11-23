"""Search calls written into the trace (W3.8: was the gold section retrieved, or did the model miss it?).

A search step has the same keys as a model-call step (tokens 0, no model, no prompt version), so code that sums over
the trace keeps working; `step == "search"` tells them apart. The hits are stored without their text: `chunk_id`
points into data/chunks.jsonl.
"""

import time
from collections.abc import Callable

STEP = "search"
HIT_FIELDS = ("chunk_id", "doc_id", "section", "version", "score", "bm25_rank", "dense_rank", "rerank_score")


def _plain(value):
    """numpy numbers as Python numbers, so the trace can be written as JSON."""
    return value.item() if hasattr(value, "item") else value


def logged(search: Callable, trace: list[dict]) -> Callable:
    """The same search (interface 2); every call is appended to `trace` with its ranked hits and latency."""

    def wrapper(query, course=None, doc_type=None, k=5, as_of=None):
        start = time.perf_counter()
        hits = search(query, course=course, doc_type=doc_type, k=k, as_of=as_of)
        trace.append(
            {
                "step": STEP,
                "attempt": 1,
                "prompt_version": None,
                "model": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_s": time.perf_counter() - start,
                "error": None,
                "query": query,
                "course": course,
                "doc_type": doc_type,
                "k": k,
                "as_of": as_of,
                "hits": [
                    {"rank": rank, **{f: _plain(hit.get(f)) for f in HIT_FIELDS}} for rank, hit in enumerate(hits, 1)
                ],
            }
        )
        return hits

    return wrapper


def model_calls(trace: list[dict]) -> list[dict]:
    """The trace without its search steps."""
    return [t for t in trace if t["step"] != STEP]
