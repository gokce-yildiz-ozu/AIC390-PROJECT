"""Temporary search with the interface 2 signature, until the real hybrid search (src/aic390/rag/) is ready.

It holds one short section per fact in the Facts table (docs/data_inventory.md §1), with the gold doc_id and
section names, and scores by word overlap. Each section has a `keywords` line in Turkish so that Turkish questions
find English text; the real search does this with multilingual embeddings (bge-m3). Nothing here is graded as
retrieval: the W3.3 ablations and W3.5 questions run on the real search.
"""

import re
from datetime import datetime

STUB_SECTIONS = [
    (
        "cs301-syllabus",
        "CS-301",
        "syllabus",
        1,
        "2026-09-14",
        "Late policy",
        "Late submissions lose 10% of the grade per day, for at most 3 days. After 3 days the submission gets 0.",
        "geç teslim gecikme kesinti ceza late penalty",
    ),
    (
        "cs301-syllabus",
        "CS-301",
        "syllabus",
        1,
        "2026-09-14",
        "Schedule",
        "Homework 3 is due on 2026-12-04 at 23:59.",
        "takvim program ödev teslim tarihi",
    ),
    (
        "cs310-syllabus-v1",
        "CS-310",
        "syllabus",
        1,
        "2026-09-14",
        "Schedule",
        "Lab 3 is due on 2026-11-06 at 23:59.",
        "takvim program lab teslim tarihi",
    ),
    (
        "cs310-syllabus-v1",
        "CS-310",
        "syllabus",
        1,
        "2026-09-14",
        "Attendance",
        "Attendance at at least 70% of the lab sessions is mandatory.",
        "devam devamsızlık yoklama zorunlu katılım",
    ),
    (
        "cs310-syllabus-v1",
        "CS-310",
        "syllabus",
        1,
        "2026-09-14",
        "Late policy",
        "Late submissions lose 5% of the grade per day, for at most 5 days. After 5 days the submission gets 0.",
        "geç teslim gecikme kesinti ceza late penalty",
    ),
    (
        "cs310-syllabus-v2",
        "CS-310",
        "syllabus",
        2,
        "2026-11-02",
        "Schedule",
        "Lab 3 is due on 2026-11-13 at 23:59. Lab 4 is due on 2026-11-27 at 23:59.",
        "takvim program lab teslim tarihi",
    ),
    (
        "cs310-syllabus-v2",
        "CS-310",
        "syllabus",
        2,
        "2026-11-02",
        "Attendance",
        "Attendance at at least 70% of the lab sessions is mandatory.",
        "devam devamsızlık yoklama zorunlu katılım",
    ),
    (
        "cs310-syllabus-v2",
        "CS-310",
        "syllabus",
        2,
        "2026-11-02",
        "Late policy",
        "Late submissions lose 5% of the grade per day, for at most 5 days. After 5 days the submission gets 0.",
        "geç teslim gecikme kesinti ceza late penalty",
    ),
    (
        "math212-syllabus",
        "MATH-212",
        "syllabus",
        1,
        "2026-09-14",
        "Schedule",
        "Lectures are on Tuesday and Thursday, 10:40-12:30. Quizzes are held in class.",
        "ders saati takvim program sınıf derste lecture time",
    ),
    (
        "academic-calendar-fall-2026",
        None,
        "calendar",
        1,
        "2026-09-01",
        "Make-up week",
        "The make-up exam week starts on 2026-11-30.",
        "telafi sınav haftası mazeret make-up exam week",
    ),
    (
        "academic-calendar-fall-2026",
        None,
        "calendar",
        1,
        "2026-09-01",
        "Withdrawal",
        "The last day to withdraw from a course this semester is 2026-12-04.",
        "dersten çekilme son gün withdraw withdrawal",
    ),
    (
        "regulation-article-9",
        None,
        "regulation",
        1,
        "2026-09-01",
        "Article 9",
        "A student may withdraw from a course until the date set in the academic calendar.",
        "yönetmelik madde dersten çekilme withdraw withdrawal",
    ),
    (
        "regulation-article-12",
        None,
        "regulation",
        1,
        "2026-09-01",
        "Article 12",
        "A student who misses an exam with a documented excuse may take the make-up exam. "
        "The document is handed in within 3 working days.",
        "yönetmelik madde telafi sınavı mazeret rapor hastalık sınava giremedim make-up exam",
    ),
    (
        "regulation-article-14",
        None,
        "regulation",
        1,
        "2026-09-01",
        "Article 14",
        "The course instructor sets the rule for late work and announces it in the syllabus.",
        "yönetmelik madde geç teslim ödev late work",
    ),
    (
        "econ101-late-policy",
        "ECON-101",
        "policy",
        1,
        "2026-09-14",
        "Late work",
        "ECON-101 does not accept late work.",
        "geç teslim kabul gecikme late work rapor ödev",
    ),
]

STOPWORDS = {
    "the",
    "is",
    "in",
    "a",
    "an",
    "of",
    "to",
    "for",
    "what",
    "when",
    "how",
    "do",
    "does",
    "my",
    "i",
    "on",
    "at",
    "and",
    "or",
    "can",
    "will",
    "be",
    "this",
    "it",
    "me",
    "bu",
    "ne",
    "mi",
    "mı",
    "mu",
    "bir",
    "ve",
    "için",
    "var",
    "zaman",
    "nasıl",
    "kaç",
    "da",
    "de",
}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.casefold()) if len(w) >= 3 and w not in STOPWORDS}


def _overlap(query: set[str], doc: set[str]) -> int:
    """Words match when one starts with the other (at least 4 letters), so "sınavına" finds "sınav"."""
    hits = 0
    for q in query:
        if any(q == d or (min(len(q), len(d)) >= 4 and (q.startswith(d) or d.startswith(q))) for d in doc):
            hits += 1
    return hits


def _family(doc_id: str) -> str:
    return re.sub(r"-v\d+$", "", doc_id)


def search(query: str, course: str | None = None, doc_type: str | None = None, k: int = 5, as_of: str | None = None):
    """Interface 2. Course filter keeps that course's documents and the general ones (calendar, regulation)."""
    day = datetime.fromisoformat(as_of).date().isoformat() if as_of else None
    valid = [s for s in STUB_SECTIONS if day is None or s[4] <= day]
    newest = {}
    for s in valid:
        newest[_family(s[0])] = max(newest.get(_family(s[0]), 0), s[3])
    query_words = _words(query)
    hits = []
    for i, (doc_id, doc_course, kind, version, _, section, text, keywords) in enumerate(valid):
        if version != newest[_family(doc_id)]:
            continue
        if course and doc_course not in (None, course):
            continue
        if doc_type and kind != doc_type:
            continue
        score = _overlap(query_words, _words(f"{doc_id} {doc_course or ''} {section} {text} {keywords}"))
        if score:
            hits.append(
                {
                    "doc_id": doc_id,
                    "section": section,
                    "version": version,
                    "text": text,
                    "score": float(score),
                    "chunk_id": f"{doc_id}#{i}",
                    "bm25_rank": None,
                    "dense_rank": None,
                    "rerank_score": None,
                }
            )
    hits.sort(key=lambda h: -h["score"])
    return hits[:k]
