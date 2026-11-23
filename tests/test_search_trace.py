"""Search calls in the trace (W3.8). Inputs are invented, not taken from a test set."""

import json
import sys
from pathlib import Path

import numpy as np

from aic390.agent.answer import rule_answer
from aic390.agent.extract import extract
from aic390.agent.searchlog import logged, model_calls
from aic390.llm import LLMResponse
from aic390.tools.deadlines import DeadlineTable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
import run_e2e  # noqa: E402

HIT = {
    "doc_id": "doc-a",
    "section": "Late policy",
    "version": 1,
    "text": "10% per day, until 10:40.",
    "score": np.float32(0.5),
    "chunk_id": "doc-a::late::0",
    "bm25_rank": 2,
    "dense_rank": np.int64(1),
    "rerank_score": None,
}
NOW = "2026-11-19T10:00:00+03:00"


def search(query, course=None, doc_type=None, k=5, as_of=None):
    return [HIT]


def empty_search(query, course=None, doc_type=None, k=5, as_of=None):
    return []


class OneReply:
    model = "scripted"

    def __init__(self, reply):
        self.reply = json.dumps(reply)

    def chat(self, messages, temperature):
        return LLMResponse(self.reply, self.model, 10, 5, 0.1)


def test_logged_search_returns_the_same_hits_and_records_rank_and_source():
    trace = []
    assert logged(search, trace)("late?", course="XX-100", as_of=NOW) == [HIT]
    (step,) = trace
    assert (step["step"], step["query"], step["course"], step["as_of"]) == ("search", "late?", "XX-100", NOW)
    assert step["hits"][0]["rank"] == 1
    assert (step["hits"][0]["doc_id"], step["hits"][0]["section"]) == ("doc-a", "Late policy")
    assert step["latency_s"] >= 0 and "text" not in step["hits"][0]
    json.dumps(trace)  # numpy scores and ranks are written as plain numbers


def test_rule_answer_logs_the_search_before_the_model_call():
    reply = {"abstain": False, "answer": "10% per day.", "citations": [1]}
    out = rule_answer("Late?", "XX-100", NOW, "en", OneReply(reply), search)
    assert [t["step"] for t in out["trace"]] == ["search", "answer"]
    assert [t["step"] for t in model_calls(out["trace"])] == ["answer"]


def test_an_empty_search_is_logged_too():
    out = rule_answer("Late?", "XX-100", NOW, "en", OneReply({}), empty_search)
    assert [(t["step"], t["hits"]) for t in out["trace"]] == [("search", [])]


def test_extraction_logs_the_search_for_an_in_class_time():
    item = {
        "course": "XX-100",
        "item": "Quiz 9",
        "item_key": "quiz9",
        "change": "new",
        "date": {"kind": "absolute", "day": 1, "month": 12, "year": 2026},
        "time": "in_class",
        "anchor": None,
    }
    case = {
        "channel": "email",
        "received_at": NOW,
        "course": "XX-100",
        "sender": "instructor:Dr. Test",
        "text": "Quiz 9 is in class on 1 December.",
    }
    out = extract(case, OneReply({"deadlines": [item]}), DeadlineTable([]), search)
    assert [t["step"] for t in out["trace"]] == ["extract", "search"]
    assert out["deadlines"][0]["due_time"] == "10:40"


def test_the_harness_does_not_read_a_search_step_as_a_wrong_prompt_version():
    trace = []
    logged(search, trace)("late?")
    assert run_e2e.prompt_mismatches([{"output": {"trace": trace}}], {"answer": "answer_v1"}) == []


def test_a_failed_extraction_is_not_shown_as_no_deadline():
    from aic390.agent.pipeline import UNREADABLE, run_case

    class Replies:
        model = "scripted"

        def __init__(self):
            self.replies = [
                json.dumps({"intent": "deadline_message", "course": "XX-100", "urgency": "normal"}),
                '{"deadlines": []]}',
                '{"deadlines": []]}',
            ]

        def chat(self, messages, temperature):
            return LLMResponse(self.replies.pop(0), self.model, 10, 5, 0.1)

    case = {
        "channel": "email",
        "received_at": NOW,
        "course": "XX-100",
        "sender": "instructor:Dr. Test",
        "text": "Essay 1 is due on 1 December.",
    }
    out = run_case(case, Replies(), search, DeadlineTable([]))
    assert out["valid"] is False and out["answer_text"] == UNREADABLE


def test_a_failed_classification_is_not_shown_as_no_deadline():
    from aic390.agent.pipeline import UNREADABLE, run_case

    case = {"channel": "email", "received_at": NOW, "course": None, "sender": "instructor:Dr. Test", "text": "Hi."}
    out = run_case(case, OneReply("not an object"), search, DeadlineTable([]))
    assert out["valid"] is False and out["answer_text"] == UNREADABLE
