import json
from pathlib import Path

import pytest

from aic390.rag.chunking import CorpusError, build_chunks, chunk_document, split_words

ROOT = Path(__file__).resolve().parent.parent

FRONT = """---
doc_id: {doc_id}
title: Test Course Syllabus
course: CS-999
doc_type: syllabus
version: 1
valid_from: 2026-09-21
language: en
audience: all
source: synthetic
reviewed: false
---
"""


def write_doc(folder: Path, doc_id: str, body: str) -> Path:
    path = folder / f"{doc_id}.md"
    path.write_text(FRONT.format(doc_id=doc_id) + body, encoding="utf-8")
    return path


def test_one_chunk_per_section_with_metadata(tmp_path):
    body = "# Title\n\n## Late policy\n\nTen percent per day.\n\n## Schedule\n\nHW1 due.\n"
    path = write_doc(tmp_path, "cs999-syllabus", body)
    chunks = chunk_document(path)
    assert [c["section"] for c in chunks] == ["Late policy", "Schedule"]
    first = chunks[0]
    assert first["chunk_id"] == "cs999-syllabus::late-policy::0"
    assert first["valid_from"] == "2026-09-21" and first["course"] == "CS-999" and first["version"] == 1
    assert first["index_text"].startswith("Test Course Syllabus | Late policy")


def test_text_before_the_first_section_joins_it(tmp_path):
    path = write_doc(tmp_path, "cs999-syllabus", "# Title\n\nThis version replaces v1.\n\n## Schedule\n\nLab 3 due.\n")
    (chunk,) = chunk_document(path)
    assert chunk["text"].startswith("This version replaces v1.") and "Lab 3 due." in chunk["text"]


def test_long_section_splits_at_sentences_and_keeps_its_section(tmp_path):
    sentence = "One two three four five six seven eight nine ten."
    path = write_doc(tmp_path, "cs999-syllabus", "## Grading\n\n" + " ".join([sentence] * 5) + "\n")
    chunks = chunk_document(path, max_words=20)
    assert len(chunks) == 3 and {c["section"] for c in chunks} == {"Grading"}
    assert [c["part"] for c in chunks] == [0, 1, 2]
    assert all(len(c["text"].split()) <= 20 for c in chunks)


def test_split_words_handles_a_sentence_longer_than_the_limit():
    parts = split_words(" ".join(["word"] * 25), max_words=10)
    assert [len(p.split()) for p in parts] == [10, 10, 5]


def test_doc_id_must_match_the_file_name(tmp_path):
    path = tmp_path / "wrong-name.md"
    path.write_text(FRONT.format(doc_id="cs999-syllabus") + "## A\n\ntext\n", encoding="utf-8")
    with pytest.raises(CorpusError):
        chunk_document(path)


def test_same_doc_id_in_two_folders_is_an_error(tmp_path):
    core, bulk = tmp_path / "core", tmp_path / "bulk"
    core.mkdir()
    bulk.mkdir()
    write_doc(core, "cs999-syllabus", "## A\n\ntext\n")
    write_doc(bulk, "cs999-syllabus", "## A\n\ntext\n")
    with pytest.raises(CorpusError):
        build_chunks([core, bulk])


def test_every_gold_source_in_the_test_sets_exists_in_the_corpus():
    """A renamed file or heading would silently fail the cases that cite it; this makes it fail here instead."""
    chunks = build_chunks([ROOT / "data/corpus", ROOT / "data/corpus_bulk"])
    available = {(c["doc_id"], c["section"].strip().lower()) for c in chunks}
    missing = set()
    for line in (ROOT / "eval/testsets/week2_cases.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        for source in json.loads(line).get("expected", {}).get("sources") or []:
            key = (source["doc_id"], source["section"].strip().lower())
            if key not in available:
                missing.add(key)
    assert not missing, f"gold sources not in the corpus: {sorted(missing)}"
