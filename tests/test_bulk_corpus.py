"""D-008 bulk corpus generator: reproducible, never a core course code, no forbidden topics, valid documents."""

import importlib.util
import re
from pathlib import Path

import pytest

from aic390.rag.chunking import build_chunks, read_document, split_sections

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("generate_bulk_corpus", ROOT / "scripts/generate_bulk_corpus.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


@pytest.fixture(scope="module")
def documents():
    return gen.generate(seed=7, courses=200)


def test_same_seed_same_output():
    assert gen.generate(seed=7, courses=30) == gen.generate(seed=7, courses=30)


def test_different_seed_different_output():
    assert gen.generate(seed=7, courses=30) != gen.generate(seed=8, courses=30)


def test_no_core_course_code_anywhere(documents):
    pattern = re.compile("|".join(re.escape(c) + "|" + re.escape(c.replace("-", "")) for c in gen.CORE_CODES), re.I)
    assert not [doc_id for doc_id, text in documents.items() if pattern.search(text)]


def test_no_forbidden_topics(documents):
    hits = [(doc_id, w) for doc_id, text in documents.items() for w in gen.FORBIDDEN_WORDS if w in text.lower()]
    assert not hits
    gen.check(documents)


def test_no_calendar_wide_dates_or_regulation_articles(documents):
    """Generated text must not compete with the calendar or the regulation, which the test sets cite."""
    words = ("make-up week", "withdraw", "article ", "madde ", "telafi haftası")
    assert not [doc_id for doc_id, text in documents.items() if any(w in text.lower() for w in words)]


def test_documents_are_valid_corpus_files(documents, tmp_path):
    for doc_id, text in documents.items():
        (tmp_path / f"{doc_id}.md").write_text(text, encoding="utf-8")
    chunks = build_chunks([tmp_path])
    assert {c["doc_id"] for c in chunks} == set(documents)
    assert {c["language"] for c in chunks} <= {"en", "tr"}
    assert all(c["audience"] == "all" for c in chunks if c["doc_type"] == "syllabus")
    assert all(c["audience"] == f"enrolled:{c['course']}" for c in chunks if c["doc_type"] == "announcement")


def test_revised_syllabus_changes_only_the_schedule(documents, tmp_path):
    v2_ids = [d for d in documents if d.endswith("-syllabus-v2")]
    assert v2_ids, "expected some revised syllabi"
    for v2_id in v2_ids[:20]:
        v1_id = v2_id[: -len("-v2")] + "-v1"
        sections = {}
        for doc_id in (v1_id, v2_id):
            path = tmp_path / f"{doc_id}.md"
            path.write_text(documents[doc_id], encoding="utf-8")
            meta, body = read_document(path)
            sections[doc_id] = dict(split_sections(body))
            assert meta["version"] == (2 if doc_id == v2_id else 1)
        changed = [name for name in sections[v1_id] if sections[v1_id][name] != sections[v2_id][name]]
        assert changed in (["Schedule"], ["Takvim"])
