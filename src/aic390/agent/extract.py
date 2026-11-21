"""W2.2 extraction: deadlines from one email or LMS announcement (interface 4).

The model only reads: it names each deadline and describes its date as an expression (prompts/extract_v1.md).
Code does the rest, so the week-1 failures cannot come back through the model:
- dates come from aic390.dates (no date arithmetic by the model);
- the old date of a moved deadline comes from the deadline table as it stood at received_at (newest version);
- "in class" times and calendar anchors come from search, and those sections are cited;
- trust comes from the sender field: only an instructor's message can add or change deadlines.
"""

import re
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aic390 import jsoncall
from aic390.agent import search_stub
from aic390.classifier import COURSE_PATTERN, format_input
from aic390.dates import DateError, resolve
from aic390.llm import ChatClient
from aic390.tools.deadlines import DeadlineTable

PROMPT_VERSION = "extract_v1"


class ExtractedDeadline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course: str = Field(pattern=COURSE_PATTERN)
    item: str
    item_key: str = Field(pattern=r"^[a-z0-9]+$")
    change: Literal["new", "update"]
    date: dict | None
    time: str | None
    anchor: str | None = None


class ExtractOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deadlines: list[ExtractedDeadline]


def is_trusted(case: dict) -> bool:
    """Only an instructor may set or change deadlines (data_inventory §4). Claims inside the text do not count."""
    return (case.get("sender") or "").startswith("instructor:")


def format_extract_input(case: dict, table: DeadlineTable, delimited: bool = False) -> str:
    """Metadata, the student's current rows for the course, then the text. A prompt that names <message> tags
    (extract_v3 onwards) gets the text inside them; earlier versions get it after "Text:", as they were run."""
    rows = [r for r in table.current(case["received_at"]) if not case.get("course") or r["course"] == case["course"]]
    listed = [
        f"- {r['course']} {r['item_key']}: {r['item']}, due "
        + (f"{r['due_date']} {r['due_time'] or '(no time)'}" if r["due_date"] else "unclear")
        for r in rows
    ]
    header, text = format_input(case).split("\n\n", 1)
    body = f"<message>\n{text}\n</message>" if delimited else f"Text:\n{text}"
    return f"{header}\n\nAlready on the list:\n" + ("\n".join(listed) or "- nothing") + f"\n\n{body}"


def _first(pattern: str, hits: list[dict]) -> tuple[str, dict] | None:
    """The first match of pattern in the search hits, with the hit's citation."""
    for hit in hits:
        match = re.search(pattern, hit["text"])
        if match:
            return match.group(1), {"doc_id": hit["doc_id"], "section": hit["section"]}
    return None


def resolve_row(item: ExtractedDeadline, case: dict, table: DeadlineTable, search: Callable) -> tuple[dict, list[dict]]:
    """One interface 5 deadline row plus the sources its date came from."""
    received_at = case["received_at"]
    sources = []
    base = table.find(received_at, item.course, item.item_key) if item.change == "update" else None
    if base and base.get("source"):
        sources.append(base["source"])
    base_date = base["due_date"] if base else None
    base_time = base["due_time"] if base else None

    time_value = item.time
    if time_value == "in_class":
        found = _first(
            r"(\d{1,2}:\d{2})",
            search(f"{item.course} lecture time schedule", course=item.course, doc_type="syllabus", as_of=received_at),
        )
        time_value = found[0].zfill(5) if found else None
        if found:
            sources.append(found[1])
    if item.anchor:
        found = _first(r"(\d{4}-\d{2}-\d{2})", search(item.anchor, doc_type="calendar", as_of=received_at))
        if found:
            base_date = found[0]
            sources.append(found[1])

    row = {
        "course": item.course,
        "item": item.item,
        "item_key": item.item_key,
        "due_date": None,
        "due_time": None,
        "due_candidates": [],
        "status": "updated" if base else "new",
        "supersedes": {"date": base["due_date"], "time": base["due_time"]} if base and base["due_date"] else None,
        "ask_user": False,
    }
    try:
        if item.date is None:
            raise DateError("no date in the text")
        row.update(resolve(item.date, time_value, received_at, base_date, base_time))
    except DateError:
        row["status"] = "unverified"  # shown to the student as "date unclear", never guessed
    return row, sources


def extract(
    case: dict,
    client: ChatClient,
    table: DeadlineTable | None = None,
    search: Callable | None = None,
    prompt_version: str = PROMPT_VERSION,
) -> dict:
    table = table or DeadlineTable.seed()
    search = search or search_stub.search
    if not is_trusted(case):
        # Checked in code before any model call: the model never decides whom to trust.
        return {
            "deadlines": [],
            "ask_user": False,
            "untrusted_flag": True,
            "action": None,
            "sources": [],
            "valid": True,
            "trace": [],
        }
    system = jsoncall.load_prompt(prompt_version)
    output, trace = jsoncall.call_json(
        client,
        system,
        format_extract_input(case, table, delimited="<message>" in system),
        ExtractOutput,
        "extract",
        prompt_version,
    )
    if output is None:
        return {
            "deadlines": [],
            "ask_user": False,
            "untrusted_flag": False,
            "action": None,
            "sources": [],
            "valid": False,
            "trace": trace,
        }
    rows, sources = [], []
    for item in output.deadlines:
        row, row_sources = resolve_row(item, case, table, search)
        rows.append(row)
        sources += [s for s in row_sources if s not in sources]
    ask_user = any([r.pop("ask_user") for r in rows])  # a list, so every row loses the helper field
    return {
        "deadlines": rows,
        "ask_user": ask_user,
        "untrusted_flag": False,
        "action": None,
        "sources": sources,
        "valid": True,
        "trace": trace,
    }
