import json
from pathlib import Path

import pytest

from aic390.classifier import FALLBACK, classify, format_input, load_prompt, parse
from aic390.llm import LLMResponse

CASES = Path(__file__).resolve().parents[1] / "eval" / "testsets" / "week2_cases.jsonl"

CASE = {
    "id": "t-1",
    "channel": "email",
    "received_at": "2026-11-09T09:10:00+03:00",
    "course": "CS-301",
    "sender": "instructor:Dr. Test",
    "text": "Homework 2 is due on 20 November at 23:59.",
    "expected": {"intent": "deadline_message"},
}


class ScriptedClient:
    """Returns the given replies in order and records every call."""

    def __init__(self, replies, error=None):
        self.model = "scripted"
        self.replies = list(replies)
        self.error = error
        self.calls = []

    def chat(self, messages, temperature):
        self.calls.append({"messages": [dict(m) for m in messages], "temperature": temperature})
        text = "" if self.error else self.replies.pop(0)
        return LLMResponse(text, self.model, 10, 5, 0.1, error=self.error)


GOOD = '{"intent": "deadline_message", "course": "CS-301", "urgency": "normal", "multi_step": false}'


def test_valid_reply_is_returned_at_temperature_zero():
    client = ScriptedClient([GOOD])
    result = classify(CASE, client)
    assert result["intent"] == "deadline_message" and result["course"] == "CS-301"
    assert result["valid"] is True
    assert len(client.calls) == 1 and client.calls[0]["temperature"] == 0.0
    assert result["trace"][0]["prompt_version"] == "classifier_v1"


def test_json_inside_a_code_fence_is_accepted():
    result = classify(CASE, ScriptedClient(["```json\n" + GOOD + "\n```"]))
    assert result["valid"] is True


def test_invalid_reply_is_retried_once_with_the_error():
    client = ScriptedClient(['{"intent": "deadline", "course": "CS-301", "urgency": "normal"}', GOOD])
    result = classify(CASE, client)
    assert result["valid"] is True and len(client.calls) == 2
    assert "not valid" in client.calls[1]["messages"][-1]["content"]
    assert result["trace"][0]["error"].startswith("schema")


def test_two_invalid_replies_give_the_fallback():
    client = ScriptedClient(["no json here", "still not"])
    result = classify(CASE, client)
    assert result["valid"] is False and len(client.calls) == 2
    assert {k: result[k] for k in FALLBACK} == FALLBACK


def test_api_error_is_not_retried_and_gives_the_fallback():
    client = ScriptedClient([], error="RateLimitError()")
    result = classify(CASE, client)
    assert result["valid"] is False and len(client.calls) == 1
    assert result["trace"][0]["error"] == "RateLimitError()"


@pytest.mark.parametrize(
    "reply",
    [
        '{"intent": "other", "course": "cs301", "urgency": "normal"}',
        '{"intent": "other", "course": null, "urgency": "soon"}',
        '{"intent": "other", "course": null, "urgency": "normal", "extra": 1}',
    ],
)
def test_schema_rejects_bad_fields(reply):
    with pytest.raises(ValueError):
        parse(reply)


def test_null_course_and_missing_multi_step_are_allowed():
    out = parse('{"intent": "rule_question", "course": null, "urgency": "high"}')
    assert out.course is None and out.multi_step is False


def test_labels_never_reach_the_model():
    text = format_input(CASE)
    assert "deadline_message" not in text and "expected" not in text
    assert text.startswith("channel: email\nreceived_at: 2026-11-09T09:10:00+03:00")


def test_prompt_names_every_intent():
    prompt = load_prompt()
    for intent in ["deadline_message", "rule_question", "lookup", "reminder", "other"]:
        assert f'"{intent}"' in prompt


def test_expected_intents_in_the_test_set_fit_the_schema():
    rows = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        reply = json.dumps({"intent": row["expected"]["intent"], "course": row["course"], "urgency": "normal"})
        parse(reply)
