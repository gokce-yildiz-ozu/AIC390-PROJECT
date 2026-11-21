"""run_case: one input through the whole pipeline (interface 4), output with the interface 5 fields.

classify -> deadline_message: extract | chat: answer | anything else: nothing to do.
The output has every field of `expected` in eval/testsets/week2_cases.jsonl except the judge-only ones
(must_include, must_not), plus answer_text, the classifier output, valid and the trace of every model call.
The harness (eval/run_e2e.py) and the demo (app/demo.py) both call this function.
"""

from collections.abc import Callable

from aic390.agent import search_stub
from aic390.agent.answer import answer, answer_language
from aic390.agent.extract import PROMPT_VERSION as extract_prompt
from aic390.agent.extract import extract
from aic390.classifier import PROMPT_VERSION as classifier_prompt
from aic390.classifier import classify
from aic390.llm import ChatClient
from aic390.tools.deadlines import DeadlineTable

STEPS = ("classifier", "extract", "answer", "lookup")


def deadline_text(result: dict) -> str:
    if result["untrusted_flag"]:
        return "Not changed: this sender cannot change your deadlines. Check the course page or ask the instructor."
    lines = [
        f"Not changed: {d['course']} {d['item']} (a message about another course cannot change it)"
        for d in result.get("dropped", [])
    ]
    if not result["deadlines"]:
        return "\n".join(lines) or "No deadline in this message."
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
    prompts: dict[str, str] | None = None,
) -> dict:
    """prompts maps a step ("classifier", "extract", "answer", "lookup") to a prompt version, e.g.
    {"extract": "extract_v2"}; a step left out uses its default version, so run_case(case, client) is unchanged."""
    prompts = prompts or {}
    unknown = set(prompts) - set(STEPS)
    if unknown:
        raise ValueError(f"unknown prompt steps: {sorted(unknown)}; expected {STEPS}")
    search = search or search_stub.search
    table = table or DeadlineTable.seed()
    cls = classify(case, client, prompts.get("classifier", classifier_prompt))
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
        result = extract(case, client, table, search, prompts.get("extract", extract_prompt))
        out.update({k: result[k] for k in ("deadlines", "ask_user", "untrusted_flag", "action", "sources")})
        out["answer_text"] = deadline_text(result)
    elif case.get("channel") == "chat":
        result = answer(case, client, search, table, intent=cls["intent"], course=cls["course"], prompts=prompts)
        out.update({k: result[k] for k in ("deadlines", "ask_user", "abstain", "sources", "action", "count")})
        out["answer_text"] = result["text"]
    else:
        out["answer_text"] = "No deadline in this message."
        return out
    out["valid"] = out["valid"] and result["valid"]
    out["trace"] += result["trace"]
    return out
