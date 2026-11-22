"""W3.4: numbered citations and fixed abstentions (answer_v2). Inputs are invented, not taken from a test set."""

import json

from aic390.agent.answer import ABSTENTIONS, NOT_FOUND, renumber, rule_answer
from aic390.llm import LLMResponse

HITS = [
    {"doc_id": "doc-a", "section": "Late policy", "text": "10% per day."},
    {"doc_id": "doc-b", "section": "Article 3", "text": "The instructor sets the rule."},
    {"doc_id": "doc-a", "section": "Late policy", "text": "At most 3 days."},
]


class OneReply:
    model = "scripted"

    def __init__(self, reply):
        self.reply = json.dumps(reply)
        self.calls = 0

    def chat(self, messages, temperature):
        self.calls += 1
        return LLMResponse(self.reply, self.model, 10, 5, 0.1)


def search_with(hits):
    return lambda query, course=None, doc_type=None, k=5, as_of=None: hits


def ask(reply, hits=HITS, language="en"):
    client = OneReply(reply)
    out = rule_answer(
        "A question?", "XX-100", "2026-11-19T10:00:00+03:00", language, client, search_with(hits), "answer_v2"
    )
    return out, client


def test_markers_are_renumbered_in_order_of_first_use():
    text, sources = renumber("The instructor decides [2]. Late work loses 10% per day [1].", HITS)
    assert text == "The instructor decides [1]. Late work loses 10% per day [2]."
    assert sources == [{"doc_id": "doc-b", "section": "Article 3"}, {"doc_id": "doc-a", "section": "Late policy"}]


def test_two_hits_of_one_section_share_a_number_and_unknown_markers_go():
    text, sources = renumber("10% per day [1], at most 3 days [3] [9].", HITS)
    assert text == "10% per day [1], at most 3 days [1]."
    assert sources == [{"doc_id": "doc-a", "section": "Late policy"}]


def test_answered_text_and_sources_match():
    out, _ = ask({"status": "answered", "answer": "Late work loses 10% per day [3] up to 3 days [1]."})
    assert out["abstain"] is False and out["text"] == "Late work loses 10% per day [1] up to 3 days [1]."
    assert out["sources"] == [{"doc_id": "doc-a", "section": "Late policy"}]


def test_an_answer_without_a_valid_source_number_is_not_shown():
    out, _ = ask({"status": "answered", "answer": "Late work is always accepted."})
    assert out["abstain"] is True and out["text"] == NOT_FOUND["en"] and out["sources"] == []


def test_each_abstention_kind_has_one_fixed_reply_in_both_languages():
    for status in ("not_in_documents", "grade_prediction", "legal_interpretation"):
        for language in ("en", "tr"):
            out, _ = ask({"status": status, "answer": "invented text 2026-05-31"}, language=language)
            assert out["text"] == ABSTENTIONS[status][language] and out["sources"] == [] and out["abstain"] is True


def test_no_hits_abstains_without_a_model_call():
    out, client = ask({"status": "answered", "answer": "x [1]"}, hits=[])
    assert out["text"] == NOT_FOUND["en"] and client.calls == 0


def test_answer_v1_keeps_its_week_2_behaviour():
    client = OneReply({"abstain": False, "answer": "10% per day.", "citations": [1]})
    out = rule_answer("Q?", None, "2026-11-19T10:00:00+03:00", "en", client, search_with(HITS))
    assert out["text"] == "10% per day." and out["sources"] == [{"doc_id": "doc-a", "section": "Late policy"}]
