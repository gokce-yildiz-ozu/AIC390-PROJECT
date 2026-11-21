"""W3.2 chunking: corpus Markdown files -> one chunk per `##` section.

A section is the citation unit (interface 3), so a chunk never crosses a `##` heading. A section longer than
`max_words` is split at sentence boundaries into parts; the chunk-size ablation (W3.7) changes only `max_words`.
Gold sources in the test sets are (doc_id, section), never chunk ids, so changing `max_words` keeps them valid.
"""

import json
import re
from datetime import date
from pathlib import Path

import yaml

REQUIRED_FIELDS = (
    "doc_id",
    "title",
    "course",
    "doc_type",
    "version",
    "valid_from",
    "language",
    "audience",
    "source",
    "reviewed",
)
DEFAULT_MAX_WORDS = 200

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class CorpusError(ValueError):
    pass


def read_document(path: Path) -> tuple[dict, str]:
    """Return (front matter, body). The file name without .md must equal doc_id."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = _FRONT_MATTER.match(text)
    if not match:
        raise CorpusError(f"{path}: no YAML front matter")
    meta = yaml.safe_load(match.group(1)) or {}
    missing = [field for field in REQUIRED_FIELDS if field not in meta]
    if missing:
        raise CorpusError(f"{path}: missing front matter fields {missing}")
    if meta["doc_id"] != path.stem:
        raise CorpusError(f"{path}: doc_id {meta['doc_id']!r} does not match the file name")
    for key, value in meta.items():
        if isinstance(value, date):
            meta[key] = value.isoformat()
    return meta, text[match.end() :]


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split a body at `##` headings. Text before the first `##` (except the `#` title) joins the first section."""
    preface: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    for line in body.split("\n"):
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
        elif not line.startswith("# "):
            preface.append(line)
    result = [(name, "\n".join(lines).strip()) for name, lines in sections]
    intro = "\n".join(preface).strip()
    if intro and result:
        name, text = result[0]
        result[0] = (name, f"{intro}\n\n{text}".strip())
    return [(name, text) for name, text in result if text]


def split_words(text: str, max_words: int) -> list[str]:
    """Split text into parts of at most max_words words, at sentence ends where possible."""
    if len(text.split()) <= max_words:
        return [text]
    parts: list[str] = []
    current: list[str] = []
    for sentence in _SENTENCE_END.split(text):
        words = sentence.split()
        if current and len(current) + len(words) > max_words:
            parts.append(" ".join(current))
            current = []
        while len(words) > max_words:
            parts.append(" ".join(words[:max_words]))
            words = words[max_words:]
        current.extend(words)
    if current:
        parts.append(" ".join(current))
    return parts


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def chunk_document(path: Path, max_words: int = DEFAULT_MAX_WORDS) -> list[dict]:
    meta, body = read_document(path)
    sections = split_sections(body)
    if not sections:
        raise CorpusError(f"{path}: no `##` sections with text")
    chunks = []
    for section, text in sections:
        for part, piece in enumerate(split_words(text, max_words)):
            chunks.append(
                {
                    "chunk_id": f"{meta['doc_id']}::{slug(section)}::{part}",
                    "doc_id": meta["doc_id"],
                    "section": section,
                    "part": part,
                    "title": meta["title"],
                    "course": meta["course"],
                    "doc_type": meta["doc_type"],
                    "version": meta["version"],
                    "valid_from": meta["valid_from"],
                    "language": meta["language"],
                    "audience": meta["audience"],
                    "text": piece,
                    # What BM25 and the embedder see: the title and section name carry the course code and topic
                    # that the section text itself often leaves out ("Late policy" never says "CS-301").
                    "index_text": f"{meta['title']} | {section}\n{piece}",
                }
            )
    return chunks


def build_chunks(corpus_dirs: list[Path], max_words: int = DEFAULT_MAX_WORDS) -> list[dict]:
    """Chunk every .md file in the given folders (missing folders are skipped), in a stable order."""
    chunks: list[dict] = []
    seen_docs: set[str] = set()
    for folder in corpus_dirs:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            if path.stem in seen_docs:
                raise CorpusError(f"{path}: doc_id {path.stem!r} appears in more than one folder")
            seen_docs.add(path.stem)
            chunks.extend(chunk_document(path, max_words))
    return chunks


def write_jsonl(chunks: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
