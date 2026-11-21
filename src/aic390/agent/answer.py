"""W2.2 / W3.4 answers to the student's chat messages (interface 4).

- rule_question: search, then the model answers only from the numbered sources and cites them, or abstains
  (prompts/answer_v1.md). No hits at all means a fixed abstention without a model call.
- lookup and reminder: the model only plans which rows the request is about (prompts/lookup_v1.md); code reads
  the deadline table, counts, and builds the reminder preview. The reply text is a template, so every date and
  number in it comes from the table.
- anything else in chat: a fixed refusal (abstain), so a prompt-extraction attempt gets nothing from the model.
"""

import re
from collections.abc import Callable
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aic390 import jsoncall
from aic390.agent import search_stub
from aic390.classifier import COURSE_PATTERN, format_input
from aic390.dates import ISTANBUL, DateError, remind_at, resolve
from aic390.llm import ChatClient
from aic390.tools.deadlines import DeadlineTable, as_listed, needs_asking

ANSWER_PROMPT = "answer_v1"
LOOKUP_PROMPT = "lookup_v1"

TURKISH_LETTERS = set("çğıöşü")
TURKISH_WORDS = {"ne", "bu", "mi", "mı", "mu", "için", "nasıl", "kaç", "zaman", "var", "hangi", "nedir", "neler"}
ENGLISH_WORDS = {"the", "is", "what", "my", "in", "on", "when", "please", "it", "how", "can", "will", "i", "a", "to"}


def answer_language(case: dict) -> str | None:
    """The language of the student's question, decided in code. Emails and announcements have none."""
    if case.get("channel") != "chat":
        return None
    words = re.findall(r"\w+", case["text"].casefold())
    # Count words, not letters, so a Turkish name in an English question ("Dr. Elif Aydın", w2-16) stays English.
    turkish = sum(w in TURKISH_WORDS or bool(TURKISH_LETTERS & set(w)) for w in words)
    english = sum(w in ENGLISH_WORDS for w in words)
    return "tr" if turkish > english else "en"


# Rule questions -----------------------------------------------------------------------------------------------


class RuleAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    abstain: bool
    answer: str
    citations: list[int] = []


NOT_FOUND = {
    "en": "I could not find this in the course documents or the regulation. Please ask your instructor, your advisor "
    "or student affairs.",
    "tr": "Bunu ders belgelerinde ya da yönetmelikte bulamadım. Lütfen dersin hocasına, danışmanına ya da öğrenci "
    "işlerine sor.",
}


def format_sources(hits: list[dict]) -> str:
    return "\n\n".join(f"[{i}] {h['doc_id']} · {h['section']}\n{h['text']}" for i, h in enumerate(hits, 1))


def rule_answer(
    question: str,
    course: str | None,
    received_at: str,
    language: str,
    client: ChatClient,
    search: Callable,
    prompt_version: str = ANSWER_PROMPT,
) -> dict:
    query = question if not course or course in question else f"{course} {question}"  # the course's own documents first
    hits = search(query, course=course, k=5, as_of=received_at)
    if not hits:
        return {"text": NOT_FOUND[language], "sources": [], "abstain": True, "valid": True, "trace": []}
    user = f"course: {course or 'none'}\nquestion: {question}\n\nSources:\n{format_sources(hits)}"
    output, trace = jsoncall.call_json(
        client, jsoncall.load_prompt(prompt_version), user, RuleAnswer, "answer", prompt_version
    )
    if output is None:
        return {"text": NOT_FOUND[language], "sources": [], "abstain": True, "valid": False, "trace": trace}
    sources = []
    if not output.abstain:
        for n in output.citations:
            if 1 <= n <= len(hits):
                source = {"doc_id": hits[n - 1]["doc_id"], "section": hits[n - 1]["section"]}
                if source not in sources:
                    sources.append(source)
    return {"text": output.answer, "sources": sources, "abstain": output.abstain, "valid": True, "trace": trace}


# Look-ups and reminders ---------------------------------------------------------------------------------------


class ReminderPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hours_before: float | None = 24
    date: dict | None = None
    time: str | None = None


class LookupPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course: str | None = Field(default=None, pattern=COURSE_PATTERN)
    item_keys: list[str] = []
    item_type: Literal["homework", "lab", "quiz", "exam", "project"] | None = None
    period: Literal["this_week", "next_week", "upcoming"] = "upcoming"
    pick: Literal["all", "nearest"] = "all"
    count: bool = False
    other_student: bool = False
    reminder: ReminderPlan | None = None
    rule_question: str | None = None


def reminder_time(plan: ReminderPlan, row: dict, received_at: str) -> str | None:
    if plan.date is not None:
        try:
            when = resolve(plan.date, plan.time, received_at)
        except DateError:
            return None
        if when["due_date"] is None:
            return None  # two readings of the reminder day: not set without asking
        clock = time.fromisoformat(when["due_time"]) if when["due_time"] else time(9, 0)
        return datetime.combine(date.fromisoformat(when["due_date"]), clock, tzinfo=ISTANBUL).isoformat()
    return remind_at(row["due_date"], row["due_time"], plan.hours_before if plan.hours_before is not None else 24)


def _when_text(row: dict, language: str) -> str:
    if row["due_date"]:
        clock = row["due_time"] or ("saat belirtilmemiş" if language == "tr" else "no time given")
        return f"{row['due_date']} {clock}"
    options = " / ".join(c["date"] for c in row["due_candidates"])
    return f"tarih belirsiz ({options})" if language == "tr" else f"date unclear ({options})"


def lookup_text(rows: list[dict], count: int | None, action: dict | None, language: str) -> str:
    tr = language == "tr"
    if not rows:
        return "Listende buna uyan bir teslim yok." if tr else "Nothing on your list matches."
    lines = [f"- {r['course']} {r['item']} · {_when_text(r, language)}" for r in rows]
    head = (
        (f"Listende {count} teslim var:" if tr else f"You have {count} on your list:")
        if count is not None
        else ("Listenden:" if tr else "From your list:")
    )
    parts = [head, *lines]
    if any(not r["due_date"] for r in rows):
        parts.append(
            "Tarihi belirsiz olanlar için hangisi doğru, teyit eder misin?"
            if tr
            else "Can you confirm the date of the unclear ones?"
        )
    if action:
        shown = action["remind_at"][:16].replace("T", " ")
        parts.append(
            f"Hatırlatma önizlemesi: {shown} · onayını bekliyor."
            if tr
            else f"Reminder preview: {shown} · waiting for your confirmation."
        )
    return "\n".join(parts)


OTHER_STUDENT = {
    "en": "I can only show your own deadlines.",
    "tr": "Yalnızca kendi teslimlerini gösterebilirim.",
}


def lookup_answer(
    case: dict,
    client: ChatClient,
    search: Callable,
    table: DeadlineTable,
    language: str,
    prompt_version: str = LOOKUP_PROMPT,
    answer_prompt: str = ANSWER_PROMPT,
) -> dict:
    received_at = case["received_at"]
    plan, trace = jsoncall.call_json(
        client, jsoncall.load_prompt(prompt_version), format_input(case), LookupPlan, "lookup", prompt_version
    )
    empty = {"sources": [], "count": None, "deadlines": [], "ask_user": False, "action": None}
    if plan is None:
        return {**empty, "text": NOT_FOUND[language], "abstain": True, "valid": False, "trace": trace}
    if plan.other_student:
        return {**empty, "text": OTHER_STUDENT[language], "abstain": True, "valid": True, "trace": trace}

    rows = table.upcoming(received_at, plan.course, plan.item_keys, plan.item_type, plan.period)
    certain = [r for r in rows if r["due_date"]]
    targets = certain[:1] if plan.pick == "nearest" else certain
    action = None
    if plan.reminder is not None and targets:
        at = reminder_time(plan.reminder, targets[0], received_at)
        if at:
            action = {"type": "create_reminder", "remind_at": at, "requires_confirmation": True}
    nearest = (targets[0] if targets else {}) if plan.pick == "nearest" else None
    ask_user = any([needs_asking(r, received_at, plan.period, nearest) for r in rows])
    count = len(rows) if plan.count else None
    text = lookup_text(rows, count, action, language)

    sources, abstain = [], False
    if plan.rule_question and targets:
        rule = rule_answer(
            plan.rule_question, targets[0]["course"], received_at, language, client, search, answer_prompt
        )
        trace += rule["trace"]
        sources = rule["sources"]
        text += "\n" + rule["text"]
    return {
        "text": text,
        "sources": sources,
        "abstain": abstain,
        "count": count,
        "deadlines": [as_listed(r) for r in rows],
        "ask_user": ask_user,
        "action": action,
        "valid": True,
        "trace": trace,
    }


# Entry point --------------------------------------------------------------------------------------------------

DECLINE = {
    "en": "I can help with your deadlines, course rules and reminders.",
    "tr": "Teslim tarihlerin, ders kuralları ve hatırlatmalar konusunda yardımcı olabilirim.",
}


def answer(
    case: dict,
    client: ChatClient,
    search: Callable | None = None,
    table: DeadlineTable | None = None,
    intent: str | None = None,
    course: str | None = None,
    prompts: dict[str, str] | None = None,
) -> dict:
    """Interface 4. intent and course come from the classifier; run_case passes them in.
    prompts: {"answer": "answer_v1", "lookup": "lookup_v1"}; a missing step uses its default version."""
    prompts = prompts or {}
    answer_prompt = prompts.get("answer", ANSWER_PROMPT)
    lookup_prompt = prompts.get("lookup", LOOKUP_PROMPT)
    search = search or search_stub.search
    table = table or DeadlineTable.seed()
    language = answer_language(case) or "en"
    base = {"count": None, "deadlines": [], "ask_user": False, "action": None, "answer_language": answer_language(case)}
    if intent == "rule_question":
        result = rule_answer(
            case["text"], course or case.get("course"), case["received_at"], language, client, search, answer_prompt
        )
        return {**base, **result}
    if intent in ("lookup", "reminder"):
        return {**base, **lookup_answer(case, client, search, table, language, lookup_prompt, answer_prompt)}
    return {**base, "text": DECLINE[language], "sources": [], "abstain": True, "valid": True, "trace": []}
