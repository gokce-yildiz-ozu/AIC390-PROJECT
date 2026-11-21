"""Hybrid search with small fakes in place of bge-m3 and the reranker; no model is downloaded."""

import zlib
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("bm25s")

from aic390.rag.chunking import build_chunks  # noqa: E402
from aic390.rag.search import CachedEmbedder, HybridSearch, normalize, tokenize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class FakeEmbedder:
    """Hashed bag of words, normalized: similar texts get similar vectors, like a (very weak) real embedder."""

    def encode(self, texts):
        vectors = np.zeros((len(texts), 256), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in tokenize(text):
                vectors[row, zlib.crc32(token.encode()) % 256] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1, norms)


class FakeReranker:
    """Prefers texts that contain every query token: enough to check that reranking reorders candidates."""

    def score(self, query, texts):
        wanted = set(tokenize(query))
        return [len(wanted & set(tokenize(t))) / max(len(wanted), 1) for t in texts]


@pytest.fixture(scope="module")
def chunks():
    return build_chunks([ROOT / "data/corpus"])


def test_normalize_handles_turkish_capitals():
    assert normalize("İSTANBUL Iğdır") == "istanbul iğdır"


def test_course_codes_also_become_one_token():
    assert {"cs", "301", "cs301"} <= set(tokenize("CS-301 late policy"))


@pytest.mark.parametrize("mode", ["bm25", "dense", "hybrid"])
def test_result_fields_match_interface_2(chunks, mode):
    engine = HybridSearch(chunks, embedder=FakeEmbedder(), reranker=FakeReranker(), mode=mode)
    results = engine.search("CS-301 late policy", k=3)
    assert len(results) == 3
    expected = {"doc_id", "section", "version", "text", "score", "chunk_id", "bm25_rank", "dense_rank", "rerank_score"}
    assert set(results[0]) == expected


def test_bm25_finds_the_exact_course_code(chunks):
    engine = HybridSearch(chunks, mode="bm25", rerank=False)
    top = engine.search("CS-301 late policy penalty", k=1)[0]
    assert (top["doc_id"], top["section"]) == ("cs301-syllabus", "Late policy")
    assert top["bm25_rank"] == 1 and top["dense_rank"] is None and top["rerank_score"] is None


def test_as_of_keeps_only_the_version_valid_then(chunks):
    engine = HybridSearch(chunks, mode="bm25", rerank=False)
    before = engine.search("CS-310 Lab 3 schedule", course="CS-310", as_of="2026-10-20T10:00:00+03:00", k=10)
    after = engine.search("CS-310 Lab 3 schedule", course="CS-310", as_of="2026-11-10T10:00:00+03:00", k=10)
    assert {r["doc_id"] for r in before} == {"cs310-syllabus-v1"}
    assert {r["doc_id"] for r in after} == {"cs310-syllabus-v2"}


def test_filters_by_course_and_doc_type(chunks):
    engine = HybridSearch(chunks, mode="bm25", rerank=False)
    results = engine.search("late work rule", doc_type="regulation", k=10)
    assert results and {r["doc_id"] for r in results} <= {
        "regulation-article-9",
        "regulation-article-12",
        "regulation-article-14",
    }
    assert all(r["doc_id"].startswith("econ101") for r in engine.search("late work", course="ECON-101", k=10))


def test_rrf_fuses_both_rankings(chunks):
    engine = HybridSearch(chunks, embedder=FakeEmbedder(), mode="hybrid", rerank=False)
    top = engine.search("make-up week", k=1)[0]
    assert top["bm25_rank"] is not None and top["dense_rank"] is not None
    assert top["score"] == pytest.approx(1 / (60 + top["bm25_rank"]) + 1 / (60 + top["dense_rank"]))


def test_reranker_score_decides_the_order(chunks):
    engine = HybridSearch(chunks, embedder=FakeEmbedder(), reranker=FakeReranker(), mode="hybrid")
    results = engine.search("last day to withdraw", k=5)
    scores = [r["rerank_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_missing_models_are_refused_early(chunks):
    with pytest.raises(ValueError):
        HybridSearch(chunks, mode="hybrid", rerank=False)
    with pytest.raises(ValueError):
        HybridSearch(chunks, mode="bm25", rerank=True)


def test_cached_embedder_encodes_each_text_once(tmp_path):
    calls = []

    def encode(texts):
        calls.append(list(texts))
        return np.ones((len(texts), 4), dtype=np.float32)

    embedder = CachedEmbedder(encode, "fake-model", cache_dir=tmp_path)
    embedder.encode(["a", "b"])
    out = embedder.encode(["b", "a", "c"])
    assert calls == [["a", "b"], ["c"]] and out.shape == (3, 4)
