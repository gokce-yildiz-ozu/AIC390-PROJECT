"""Check the W3.5 retrieval questions before they are frozen.

    python eval/check_retrieval_questions.py                       # eval/testsets/retrieval_questions.jsonl
    python eval/check_retrieval_questions.py --allow-empty         # while questions are still being written

Errors (exit 1): fewer than 30 questions, duplicate ids, unknown language or kind, empty question, a gold
doc_id or section that does not exist in data/corpus/, a question about a course document that does not name the
course code, a versioned document without an `as_of` that selects the gold version.
Warnings: content words shared with the gold section ("paraphrase" questions should share almost none), six or
more words in a row taken from week2_cases.jsonl, corpus sections no question points to.
Prints the sha256 of the file with LF line endings, for the freeze line in eval/testsets/README.md.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus"
DEFAULT_QUESTIONS = ROOT / "eval" / "testsets" / "retrieval_questions.jsonl"
CASES = ROOT / "eval" / "testsets" / "week2_cases.jsonl"
MIN_QUESTIONS = 30
LANGUAGES = {"tr", "en"}
KINDS = {"direct", "paraphrase", "confusable", "version", "multi"}
REQUIRED = ("id", "question", "language", "kind", "as_of", "gold")
WORD = re.compile(r"\w+", re.UNICODE)
STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "what",
    "when",
    "which",
    "does",
    "have",
    "their",
    "there",
    "after",
    "before",
    "about",
    "into",
    "each",
    "only",
    "must",
    "will",
    "they",
    "course",
    "fall",
    "2026",
}


def load_corpus(corpus: Path) -> dict[str, dict]:
    docs = {}
    for path in sorted(corpus.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        _, front, body = text.split("---", 2)
        meta = {}
        for line in front.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
        sections, current = {}, None
        for line in body.splitlines():
            if line.startswith("## "):
                current = line[3:].strip()
                sections[current] = ""
            elif current:
                sections[current] += line + "\n"
        meta["sections"] = sections
        docs[meta["doc_id"]] = meta
    return docs


def base_id(doc_id: str) -> str:
    return re.sub(r"-v\d+$", "", doc_id)


def valid_version(docs: dict, gold_id: str, as_of: str | None) -> bool:
    """True if as_of falls in the gold version's validity window (valid_from of the next version excluded)."""
    family = sorted(
        (d["valid_from"], i) for i, d in docs.items() if base_id(i) == base_id(gold_id) and d.get("valid_from")
    )
    if len(family) < 2:
        return True
    if not as_of:
        return False
    day = as_of[:10]
    starts = [start for start, _ in family]
    pos = [i for _, i in family].index(gold_id)
    after_start = day >= starts[pos]
    before_next = pos + 1 == len(starts) or day < starts[pos + 1]
    return after_start and before_next


def names_course(question: str, course: str) -> bool:
    letters, digits = course.split("-")
    return re.search(rf"\b{letters}\s*-?\s*{digits}\b", question, re.IGNORECASE) is not None


def content_words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if len(w) >= 4 and w not in STOP and not w.isdigit()}


def shingles(text: str, n: int = 6) -> set[tuple[str, ...]]:
    words = WORD.findall(text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def check(rows: list[dict], docs: dict, cases_text: str, allow_empty: bool) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if len(rows) < MIN_QUESTIONS:
        errors.append(f"{len(rows)} questions, W3.5 needs at least {MIN_QUESTIONS}")
    for i, n in Counter(r.get("id") for r in rows).items():
        if n > 1:
            errors.append(f"duplicate id {i}")
    case_shingles = shingles(cases_text)
    covered = set()
    for r in rows:
        rid = r.get("id", "?")
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            errors.append(f"{rid}: missing {', '.join(missing)}")
            continue
        if r["language"] not in LANGUAGES:
            errors.append(f"{rid}: language {r['language']!r}")
        if r["kind"] not in KINDS:
            errors.append(f"{rid}: kind {r['kind']!r}")
        q = r["question"].strip()
        if not q and not allow_empty:
            errors.append(f"{rid}: empty question")
        if not r["gold"]:
            errors.append(f"{rid}: no gold passage")
        if r["kind"] == "multi" and len(r["gold"]) < 2:
            errors.append(f"{rid}: kind multi needs two gold passages")
        for g in r["gold"]:
            doc = docs.get(g["doc_id"])
            if doc is None:
                errors.append(f"{rid}: unknown doc_id {g['doc_id']}")
                continue
            if g["section"] not in doc["sections"]:
                errors.append(f"{rid}: {g['doc_id']} has no section {g['section']!r}")
                continue
            covered.add((g["doc_id"], g["section"]))
            if not valid_version(docs, g["doc_id"], r["as_of"]):
                errors.append(f"{rid}: {g['doc_id']} has other versions; as_of must select this one")
            if not q:
                continue
            course = doc.get("course")
            if course and course != "null" and not names_course(q, course):
                errors.append(f"{rid}: question about {course} does not name {course}")
            shared = content_words(q) & content_words(doc["sections"][g["section"]])
            if r["kind"] == "paraphrase" and len(shared) > 2:
                warnings.append(f"{rid}: paraphrase shares {len(shared)} words with the gold section: {sorted(shared)}")
        if q and shingles(q) & case_shingles:
            warnings.append(f"{rid}: six or more words in a row also appear in week2_cases.jsonl")
    for doc_id, doc in docs.items():
        for section in doc["sections"]:
            if (doc_id, section) not in covered:
                warnings.append(f"no question points to {doc_id} / {section}")
    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", type=Path, default=DEFAULT_QUESTIONS)
    ap.add_argument("--allow-empty", action="store_true", help="accept empty questions while drafting")
    args = ap.parse_args()

    raw = args.path.read_bytes().replace(b"\r\n", b"\n")
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    docs = load_corpus(CORPUS)
    cases_text = " ".join(json.loads(line)["text"] for line in CASES.read_text(encoding="utf-8").splitlines() if line)
    errors, warnings = check(rows, docs, cases_text, args.allow_empty)

    langs = Counter(r.get("language") for r in rows)
    kinds = Counter(r.get("kind") for r in rows)
    filled = sum(1 for r in rows if r.get("question", "").strip())
    print(f"{len(rows)} questions, {filled} written · language {dict(langs)} · kind {dict(kinds)}")
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("ERROR:", e)
    print("sha256 (LF):", hashlib.sha256(raw).hexdigest())
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
