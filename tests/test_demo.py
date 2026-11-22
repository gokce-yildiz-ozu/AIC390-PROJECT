import json
from pathlib import Path

from aic390 import demo
from aic390.llm import LLMResponse

CASES_FILE = Path(__file__).resolve().parents[1] / "eval/testsets/week2_cases.jsonl"


class ScriptedClient:
    def __init__(self, *replies):
        self.model = "scripted"
        self.replies = [json.dumps(r) for r in replies]

    def chat(self, messages, temperature):
        return LLMResponse(self.replies.pop(0), self.model, 10, 5, 0.1)


def example(example_id):
    return next(e["case"] for e in demo.EXAMPLES if e["id"] == example_id)


def test_demo_examples_are_not_test_set_cases():
    texts = {json.loads(line)["text"] for line in CASES_FILE.read_text(encoding="utf-8").splitlines() if line}
    assert not texts & {e["case"]["text"] for e in demo.EXAMPLES}


def test_run_demo_records_what_search_returned():
    cls = {"intent": "rule_question", "course": "CS-301", "urgency": "normal", "multi_step": False}
    reply = {"abstain": False, "answer": "10% per day.", "citations": [1]}
    record = demo.run_demo(example("demo-rule"), ScriptedClient(cls, reply), "stub", demo.make_search("stub"))
    assert record["mode"] == "live" and record["search_backend"] == "stub"
    assert record["retrieved"][0]["hits"][0]["doc_id"] == "cs301-syllabus"
    assert record["output"]["sources"] == [{"doc_id": "cs301-syllabus", "section": "Late policy"}]
    assert record["route"].startswith("rule question")


def test_untrusted_sender_route_says_no_extraction_call():
    cls = {"intent": "deadline_message", "course": "CS-301", "urgency": "normal", "multi_step": False}
    record = demo.run_demo(example("demo-untrusted"), ScriptedClient(cls), "stub", demo.make_search("stub"))
    assert record["output"]["untrusted_flag"] is True and "no extraction call" in record["route"]


def test_replay_returns_the_newest_saved_run_marked_as_replay(tmp_path):
    path = tmp_path / "replay.jsonl"
    for n in (1, 2):
        demo.save_replay({"mode": "live", "search_backend": "bm25", "n": n}, "demo-rule", path)
    demo.save_replay({"mode": "live", "search_backend": "stub", "n": 3}, "demo-rule", path)
    found = demo.load_replay("demo-rule", "bm25", path)
    assert found["n"] == 2 and found["mode"] == "replay"
    assert demo.load_replay("demo-lookup", "bm25", path) is None


def test_every_example_has_a_saved_live_run_for_the_replay_fallback():
    for e in demo.EXAMPLES:
        record = demo.load_replay(e["id"], "bm25")
        assert record is not None and record["case"]["text"] == e["case"]["text"], e["id"]
