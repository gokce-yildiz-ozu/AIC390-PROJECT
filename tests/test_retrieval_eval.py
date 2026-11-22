"""eval/retrieval.py with fake models and invented questions; it never reads the frozen retrieval questions."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("bm25s")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
import retrieval  # noqa: E402

from aic390.rag.chunking import build_chunks, write_jsonl  # noqa: E402


def hit(doc_id, section):
    return {"doc_id": doc_id, "section": section}


def test_score_question_ranks_hits_and_all():
    hits = [hit("a", "x"), hit("b", "y"), hit("a", "x"), hit("c", "z"), hit("d", "w"), hit("e", "v")]
    one = retrieval.score_question([hit("b", "y")], hits)
    assert one["first_gold_rank"] == 2 and one["reciprocal_rank"] == 0.5
    assert not one["hit_at_1"] and one["hit_at_3"] and one["hit_at_5"]

    multi = retrieval.score_question([hit("a", "x"), hit("e", "v")], hits)
    assert multi["gold_ranks"] == [1, 6]  # a repeated passage counts at its first chunk
    assert multi["hit_at_1"] and not multi["all_at_5"] and multi["all_at_10"]

    miss = retrieval.score_question([hit("q", "q")], hits)
    assert miss["first_gold_rank"] is None and miss["reciprocal_rank"] == 0.0 and not miss["hit_at_10"]


def test_bootstrap_interval_is_reproducible_and_contains_the_mean():
    values = [1.0, 0.5, 0.0, 1.0, 0.25, 0.0, 1.0]
    ci = retrieval.mean_bootstrap_ci(values)
    assert ci == retrieval.mean_bootstrap_ci(values)
    assert ci[0] <= sum(values) / len(values) <= ci[1]


@pytest.fixture()
def setup(tmp_path):
    chunks = build_chunks([ROOT / "data" / "corpus"])
    chunks_path = tmp_path / "chunks.jsonl"
    write_jsonl(chunks, chunks_path)
    general = next(c for c in chunks if c["course"] is None)
    other = next(c for c in chunks if c["course"] is not None)
    rows = [
        {"id": "t1", "question": general["index_text"], "language": "en", "kind": "direct", "as_of": None,
         "gold": [hit(general["doc_id"], general["section"])]},
        {"id": "t2", "question": "SECRET-WORDING about nothing in the corpus", "language": "tr", "kind": "paraphrase",
         "as_of": None, "gold": [hit("no-such-doc", "Nothing")]},
        {"id": "t3", "question": other["index_text"], "language": "en", "kind": "multi", "as_of": None,
         "gold": [hit(other["doc_id"], other["section"]), hit("no-such-doc", "Nothing")]},
    ]  # fmt: skip
    questions = tmp_path / "questions.jsonl"
    questions.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path, questions, chunks_path


def run(tmp_path, questions, chunks_path, *extra):
    argv = ["--fake", "--questions", str(questions), "--chunks", str(chunks_path), "--results-dir", str(tmp_path)]
    retrieval.main([*argv, *extra])
    return next(p for p in tmp_path.iterdir() if p.is_dir() and p.name.endswith("_" + extra[-1]))


def test_run_writes_numbers_ids_and_no_question_text(setup):
    tmp_path, questions, chunks_path = setup
    out = run(tmp_path, questions, chunks_path, "--label", "fake-hybrid")
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))

    assert summary["overall"]["n"] == 3
    assert summary["overall"]["hit_at_1"]["k"] >= 1  # t1 asks with the passage's own text
    assert "t2" in summary["misses_at_5"]
    assert summary["multi_all_at_k"]["all_at_10"]["k"] == 0  # one gold passage of t3 does not exist
    assert summary["model_calls"] == 0
    assert not summary["reportable"]
    assert any("fake" in p for p in summary["problems"])
    assert config["questions"]["frozen"] is False  # an invented file has no recorded sha256
    assert config["search"]["course"] is None

    shown = (out / "summary.md").read_text(encoding="utf-8") + (out / "summary.json").read_text(encoding="utf-8")
    assert "SECRET-WORDING" not in shown
    assert "SECRET-WORDING" not in (out / "per_question.jsonl").read_text(encoding="utf-8")


def test_compare_counts_discordant_questions(setup):
    tmp_path, questions, chunks_path = setup
    a = run(tmp_path, questions, chunks_path, "--label", "fake-a")
    b = run(tmp_path, questions, chunks_path, "--mode", "bm25", "--no-rerank", "--label", "fake-b")
    result = retrieval.compare(a, b, "hit_at_5", tmp_path)
    assert result["n"] == 3
    assert result["b_count"] == len(result["only_a_ids"]) and result["c_count"] == len(result["only_b_ids"])
    assert result["note"] is not None  # b + c < 6 with three questions
    assert 0.0 <= result["mcnemar_exact_p"] <= 1.0


def test_compare_refuses_runs_on_different_chunks(setup):
    tmp_path, questions, chunks_path = setup
    a = run(tmp_path, questions, chunks_path, "--label", "fake-c")
    fewer = tmp_path / "fewer.jsonl"
    fewer.write_text("".join(chunks_path.read_text(encoding="utf-8").splitlines(keepends=True)[:-1]), encoding="utf-8")
    b = run(tmp_path, questions, fewer, "--label", "fake-d")
    with pytest.raises(SystemExit, match="different chunks"):
        retrieval.compare(a, b, "hit_at_5", tmp_path)


def test_frozen_hash_is_read_from_the_testsets_readme():
    recorded = retrieval.recorded_sha256(ROOT / "eval" / "testsets" / "retrieval_questions.jsonl")
    assert recorded is not None and len(recorded) == 64
