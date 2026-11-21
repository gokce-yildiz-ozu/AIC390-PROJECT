"""W3.3 hybrid search (D-007): BM25 + dense embeddings, fused with reciprocal rank fusion, then a reranker.

Interface 2: `search(query, course=None, doc_type=None, k=5, as_of=None)` returns a list of
`{doc_id, section, version, text, score, chunk_id, bm25_rank, dense_rank, rerank_score}`.

The embedder and the reranker are passed in, so tests use small fakes and the real models (BAAI/bge-m3,
BAAI/bge-reranker-v2-m3) load only where they are needed. `mode` and `rerank` exist for the W3.7 ablations.
"""

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CHUNKS = ROOT / "data" / "chunks.jsonl"
DEFAULT_CACHE = ROOT / ".cache" / "embeddings"
EMBEDDING_MODEL = "BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

_VERSION_SUFFIX = re.compile(r"-v\d+$")
_CODE = re.compile(r"\b([a-z]+)-(\d+)\b")
_TOKEN = re.compile(r"\w+")


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> np.ndarray: ...


class Reranker(Protocol):
    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


def normalize(text: str) -> str:
    """Lowercase that is safe for Turkish: 'İ' -> 'i' and 'I' -> 'i' without a stray combining dot."""
    text = text.replace("İ", "i").replace("I", "i").lower()
    return unicodedata.normalize("NFC", text.replace("̇", ""))


def tokenize(text: str) -> list[str]:
    """Word tokens, plus each course code joined ("cs-301" also gives "cs301") so BM25 can match it exactly."""
    text = normalize(text)
    return _TOKEN.findall(text) + [a + b for a, b in _CODE.findall(text)]


def doc_family(doc_id: str) -> str:
    """cs310-syllabus-v2 -> cs310-syllabus: versions of one document share a family."""
    return _VERSION_SUFFIX.sub("", doc_id)


def rank_positions(scores: np.ndarray, allowed: np.ndarray, top_n: int) -> dict[int, int]:
    """Chunk index -> 1-based rank for the top_n allowed chunks with a positive score."""
    order = [i for i in np.argsort(-scores, kind="stable") if allowed[i] and scores[i] > 0]
    return {int(i): rank for rank, i in enumerate(order[:top_n], start=1)}


class HybridSearch:
    def __init__(
        self,
        chunks: list[dict],
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        mode: str = "hybrid",
        rerank: bool = True,
        top_n: int = 20,
        rrf_k: int = 60,
    ):
        if mode not in ("hybrid", "bm25", "dense"):
            raise ValueError(f"unknown mode {mode!r}")
        if mode != "bm25" and embedder is None:
            raise ValueError(f"mode {mode!r} needs an embedder")
        if rerank and reranker is None:
            raise ValueError("rerank=True needs a reranker")
        self.chunks = chunks
        self.embedder, self.reranker = embedder, reranker
        self.mode, self.rerank, self.top_n, self.rrf_k = mode, rerank, top_n, rrf_k
        self._bm25 = None
        if mode != "dense":
            import bm25s

            self._bm25 = bm25s.BM25()
            self._bm25.index([tokenize(c["index_text"]) for c in chunks], show_progress=False)
        self._vectors = embedder.encode([c["index_text"] for c in chunks]) if mode != "bm25" else None

    def _allowed(self, course: str | None, doc_type: str | None, as_of: str | None) -> np.ndarray:
        allowed = np.array(
            [
                (course is None or c["course"] == course) and (doc_type is None or c["doc_type"] == doc_type)
                for c in self.chunks
            ]
        )
        if as_of is None:
            return allowed
        # Per document family, keep only the newest version already valid at as_of (CS-310 v1 / v2).
        valid_from = {}
        for c in self.chunks:
            if str(c["valid_from"]) <= as_of[:10]:
                family = doc_family(c["doc_id"])
                valid_from[family] = max(valid_from.get(family, ""), str(c["valid_from"]))
        current = np.array([valid_from.get(doc_family(c["doc_id"])) == str(c["valid_from"]) for c in self.chunks])
        return allowed & current

    def search(
        self, query: str, course: str | None = None, doc_type: str | None = None, k: int = 5, as_of: str | None = None
    ) -> list[dict]:
        allowed = self._allowed(course, doc_type, as_of)
        bm25_ranks: dict[int, int] = {}
        dense_ranks: dict[int, int] = {}
        if self._bm25 is not None:
            bm25_ranks = rank_positions(np.asarray(self._bm25.get_scores(tokenize(query))), allowed, self.top_n)
        if self._vectors is not None:
            query_vector = self.embedder.encode([query])[0]
            dense_ranks = rank_positions(self._vectors @ query_vector + 1.0, allowed, self.top_n)

        fused: dict[int, float] = {}
        for ranks in (bm25_ranks, dense_ranks):
            for i, rank in ranks.items():
                fused[i] = fused.get(i, 0.0) + 1.0 / (self.rrf_k + rank)
        candidates = sorted(fused, key=lambda i: (-fused[i], i))[: self.top_n]

        rerank_scores: dict[int, float] = {}
        if self.rerank and candidates:
            scores = self.reranker.score(query, [self.chunks[i]["index_text"] for i in candidates])
            rerank_scores = dict(zip(candidates, (float(s) for s in scores), strict=True))
            candidates.sort(key=lambda i: (-rerank_scores[i], -fused[i], i))

        results = []
        for i in candidates[:k]:
            c = self.chunks[i]
            results.append(
                {
                    "doc_id": c["doc_id"],
                    "section": c["section"],
                    "version": c["version"],
                    "text": c["text"],
                    "score": rerank_scores.get(i, fused[i]),
                    "chunk_id": c["chunk_id"],
                    "bm25_rank": bm25_ranks.get(i),
                    "dense_rank": dense_ranks.get(i),
                    "rerank_score": rerank_scores.get(i),
                }
            )
        return results


def load_chunks(path: Path = DEFAULT_CHUNKS) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class CachedEmbedder:
    """Wraps an encode function; vectors are cached on disk by a hash of model name and text (not committed)."""

    def __init__(self, encode: Callable[[list[str]], np.ndarray], model_name: str, cache_dir: Path = DEFAULT_CACHE):
        self._encode, self.model_name, self.cache_dir = encode, model_name, cache_dir

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model_name}\n{text}".encode()).hexdigest()

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        paths = [self.cache_dir / f"{self._key(t)}.npy" for t in texts]
        missing = [i for i, p in enumerate(paths) if not p.exists()]
        if missing:
            vectors = self._encode([texts[i] for i in missing])
            for i, vector in zip(missing, vectors, strict=True):
                np.save(paths[i], np.asarray(vector, dtype=np.float32))
        return np.stack([np.load(p) for p in paths])


def default_embedder() -> CachedEmbedder:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL)

    def encode(texts: list[str]) -> np.ndarray:
        return model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=len(texts) > 100)

    return CachedEmbedder(encode, EMBEDDING_MODEL)


class CrossEncoderReranker:
    def __init__(self, model_name: str = RERANKER_MODEL):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        return [float(s) for s in self.model.predict([(query, t) for t in texts])]


_default: HybridSearch | None = None


def search(
    query: str, course: str | None = None, doc_type: str | None = None, k: int = 5, as_of: str | None = None
) -> list[dict]:
    """Interface 2 with the full default configuration. The first call loads both models and builds the index."""
    global _default
    if _default is None:
        _default = HybridSearch(load_chunks(), embedder=default_embedder(), reranker=CrossEncoderReranker())
    return _default.search(query, course=course, doc_type=doc_type, k=k, as_of=as_of)
