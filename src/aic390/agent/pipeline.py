"""run_case: one input through the whole pipeline (interface 4), output with the interface 5 fields.

classify -> deadline_message: extract | chat: answer | anything else: nothing to do.
The output has every field of `expected` in eval/testsets/week2_cases.jsonl except the judge-only ones
(must_include, must_not), plus answer_text, the classifier output, valid and the trace of every model call.
The harness (eval/run_e2e.py) and the demo (app/demo.py) both call this function.
"""

from collections.abc import Callable

from aic390.agent import search_stub
from aic390.agent.answer import answer, answer_language
from aic390.agent.extract import extract
from aic390.classifier import classify
from aic390.llm import ChatClient
from aic390.tools.deadlines import DeadlineTable


def deadline_text(result: dict) -> str:
    if result["untrusted_flag"]:
        return "Not changed: this sender cannot change your deadlines. Check the course page or ask the instructor."
    if not result["deadlines"]:
        return "No deadline in this message."
    lines = []
    for r in result["deadlines"]:
        if r["due_date"]:
            when = f"{r['due_date']} {r['due_time'] or '(no time given)'}"
        elif r["due_candidates"]:
            when = "date unclear: " + " or ".join(c["date"] for c in r["due_candidates"]) + " - please confirm"
        else:
            when = "date unclear - please check the message"
        was = f" (was {r['supersedes']['date']} {r['supersedes']['time'] or ''})".rstrip() if r["supersedes"] else ""
        lines.append(f"{r['status'].capitalize()}: {r['course']} {r['item']} · {when}{was}")
    return "\n".join(lines)


def run_case(
    case: dict,
    client: ChatClient,
    search: Callable | None = None,
    table: DeadlineTable | None = None,
) -> dict:
    search = search or search_stub.search
    table = table or DeadlineTable.seed()
    cls = classify(case, client)
    out = {
        "intent": cls["intent"],
        "deadlines": [],
        "ask_user": False,
        "abstain": False,
        "sources": [],
        "action": None,
        "count": None,
        "untrusted_flag": False,
        "answer_language": answer_language(case),
        "answer_text": "",
        "classifier": {k: cls[k] for k in ("intent", "course", "urgency", "multi_step")},
        "valid": cls["valid"],
        "trace": list(cls["trace"]),
    }
    if cls["intent"] == "deadline_message":
        result = extract(case, client, table, search)
        out.update({k: result[k] for k in ("deadlines", "ask_user", "untrusted_flag", "action", "sources")})
        out["answer_text"] = deadline_text(result)
    elif case.get("channel") == "chat":
        result = answer(case, client, search, table, intent=cls["intent"], course=cls["course"])
        out.update({k: result[k] for k in ("deadlines", "ask_user", "abstain", "sources", "action", "count")})
        out["answer_text"] = result["text"]
    else:
        out["answer_text"] = "No deadline in this message."
        return out
    out["valid"] = out["valid"] and result["valid"]
    out["trace"] += result["trace"]
    return out
