"""extract / answer / run_case with scripted model replies: the code around the model, checked case by case.

Every expected value comes from eval/testsets/week2_cases.jsonl (the case id is in the test name).
"""

import json
from pathlib import Path

from aic390.agent.answer import answer, answer_language
from aic390.agent.extract import extract
from aic390.agent.pipeline import run_case
from aic390.agent.search_stub import search
from aic390.llm import LLMResponse
from aic390.tools.deadlines import DeadlineTable

CASES = {
    row["id"]: row
    for row in map(
        json.loads,
        (Path(__file__).resolve().parents[1] / "eval/testsets/week2_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines(),
    )
}
TABLE = DeadlineTable.seed()


class ScriptedClient:
    def __init__(self, *replies):
        self.model = "scripted"
        self.replies = [r if isinstance(r, str) else json.dumps(r) for r in replies]
        self.calls = []

    def chat(self, messages, temperature):
        self.calls.append(messages)
        return LLMResponse(self.replies.pop(0), self.model, 10, 5, 0.1)


def item(**fields):
    return {
        "course": None,
        "item": None,
        "item_key": None,
        "change": "new",
        "date": None,
        "time": None,
        "anchor": None,
        **fields,
    }


def rows(result):
    return {(r["course"], r["item_key"]): r for r in result["deadlines"]}


def expected_rows(case_id):
    return {(r["course"], r["item_key"]): r for r in CASES[case_id]["expected"]["deadlines"]}


def same_rows(result, case_id, fields=("due_date", "due_time", "due_candidates", "status", "supersedes")):
    got, want = rows(result), expected_rows(case_id)
    assert got.keys() == want.keys()
    for key in want:
        assert {f: got[key][f] for f in fields} == {f: want[key][f] for f in fields}


def run_extract(case_id, *deadlines):
    client = ScriptedClient({"deadlines": list(deadlines)})
    return extract(CASES[case_id], client, TABLE, search), client


# extract -------------------------------------------------------------------------------------------------------


def test_w1_05_move_uses_the_old_date_from_the_table():
    result, _ = run_extract(
        "w1-05",
        item(
            course="CS-301",
            item="Homework 2",
            item_key="hw2",
            change="update",
            date={"kind": "weekday_after_base", "weekday": "monday"},
            time="same",
        ),
    )
    same_rows(result, "w1-05")
    assert result["sources"] == []


def test_w1_06_base_is_the_syllabus_version_valid_at_received_at_and_is_cited():
    result, _ = run_extract(
        "w1-06",
        item(
            course="CS-310",
            item="Lab 3",
            item_key="lab3",
            change="update",
            date={"kind": "shift", "days": 7},
            time="same",
        ),
    )
    same_rows(result, "w1-06")
    assert result["sources"] == CASES["w1-06"]["expected"]["sources"]


def test_w1_03_in_class_takes_the_lecture_time_from_the_syllabus():
    result, _ = run_extract(
        "w1-03",
        item(
            course="MATH-212",
            item="Quiz 3",
            item_key="quiz3",
            date={"kind": "absolute", "day": 12, "month": 11, "year": None},
            time="in_class",
        ),
        item(
            course="MATH-212",
            item="Project milestone 1",
            item_key="milestone1",
            date={"kind": "absolute", "day": 23, "month": 11, "year": None},
            time="17:00",
        ),
    )
    same_rows(result, "w1-03")
    assert result["sources"] == [{"doc_id": "math212-syllabus", "section": "Schedule"}]


def test_w1_08_anchor_from_the_calendar_and_no_invented_time():
    result, _ = run_extract(
        "w1-08",
        item(
            course="MATH-212",
            item="Problem Set 4",
            item_key="ps4",
            date={"kind": "shift", "days": -1},
            anchor="make-up week",
        ),
    )
    same_rows(result, "w1-08")
    assert result["sources"] == CASES["w1-08"]["expected"]["sources"]


def test_w1_02_two_readings_ask_the_user():
    result, _ = run_extract(
        "w1-02",
        item(
            course="CS-301",
            item="Lab Report 3",
            item_key="labreport3",
            date={"kind": "weekday", "weekday": "friday", "modifier": "next"},
            time="23:59",
        ),
    )
    same_rows(result, "w1-02")
    assert result["ask_user"] is True


def test_w2_01_extension_without_a_date_in_the_message():
    result, _ = run_extract(
        "w2-01",
        item(
            course="CS-301",
            item="Homework 3",
            item_key="hw3",
            change="update",
            date={"kind": "shift", "days": 7},
            time="same",
        ),
    )
    same_rows(result, "w2-01")
    assert result["sources"] == CASES["w2-01"]["expected"]["sources"]


def test_unresolvable_date_is_unverified_not_guessed():
    result, _ = run_extract("w1-01", item(course="CS-301", item="Homework 2", item_key="hw2", date=None))
    assert result["deadlines"][0]["status"] == "unverified" and result["deadlines"][0]["due_date"] is None


def test_w1_25_and_w2_16_untrusted_senders_never_reach_the_model():
    for case_id in ("w1-25", "w2-16"):
        client = ScriptedClient()
        result = extract(CASES[case_id], client, TABLE, search)
        assert result["untrusted_flag"] is True and result["deadlines"] == [] and client.calls == []


def test_the_model_sees_the_list_but_never_the_labels():
    _, client = run_extract("w1-05")
    user = client.calls[0][1]["content"]
    assert "CS-301 hw2: Homework 2, due 2026-11-20 23:59" in user
    assert "expected" not in user and "2026-11-23" not in user


# answer --------------------------------------------------------------------------------------------------------


def test_answer_language_is_decided_in_code():
    assert [answer_language(CASES[i]) for i in ("w1-09", "w1-11", "w1-15", "w1-20", "w1-01")] == [
        "en",
        "tr",
        "tr",
        "tr",
        None,
    ]


def test_w1_10_rule_answer_cites_the_numbered_sources():
    reply = {"abstain": False, "answer": "2026-12-04.", "citations": [1, 2]}
    result = answer(CASES["w1-10"], ScriptedClient(reply), search, TABLE, intent="rule_question")
    assert {(s["doc_id"], s["section"]) for s in result["sources"]} == {
        ("regulation-article-9", "Article 9"),
        ("academic-calendar-fall-2026", "Withdrawal"),
    }


def test_w1_20_no_hits_abstains_without_a_model_call():
    client = ScriptedClient()
    result = answer(CASES["w1-20"], client, search, TABLE, intent="rule_question")
    assert result["abstain"] is True and result["sources"] == [] and client.calls == []
    assert result["answer_language"] == "tr"


def test_abstaining_answer_cites_nothing():
    reply = {"abstain": True, "answer": "Ask the instructor.", "citations": [1]}
    result = answer(CASES["w1-19"], ScriptedClient(reply), search, TABLE, intent="rule_question")
    assert result["abstain"] is True and result["sources"] == []


def test_w1_15_count_comes_from_the_table():
    plan = {"course": "CS-301", "count": True}
    result = answer(CASES["w1-15"], ScriptedClient(plan), search, TABLE, intent="lookup")
    same_rows(result, "w1-15")
    assert result["count"] == 3
    assert result["ask_user"] is False  # both readings of Lab Report 3 are still ahead: the count is 3 either way


def test_w1_14_this_week_lists_the_unclear_row_and_asks():
    result = answer(CASES["w1-14"], ScriptedClient({"period": "this_week"}), search, TABLE, intent="lookup")
    same_rows(result, "w1-14")
    assert result["ask_user"] is True


def test_w1_17_reminder_is_due_minus_24_hours_and_needs_confirmation():
    plan = {"course": "CS-301", "item_keys": ["hw2"], "reminder": {"hours_before": 24}}
    result = answer(CASES["w1-17"], ScriptedClient(plan), search, TABLE, intent="reminder")
    assert result["action"] == CASES["w1-17"]["expected"]["action"]


def test_w1_18_reminder_only_for_the_certain_row():
    plan = {"period": "next_week", "reminder": {"hours_before": 24}}
    result = answer(CASES["w1-18"], ScriptedClient(plan), search, TABLE, intent="reminder")
    same_rows(result, "w1-18")
    assert result["action"] == CASES["w1-18"]["expected"]["action"] and result["ask_user"] is True


def test_w2_05_reminder_at_a_stated_moment():
    plan = {
        "item_keys": ["milestone1"],
        "course": "MATH-212",
        "reminder": {
            "hours_before": None,
            "date": {"kind": "weekday", "weekday": "sunday", "modifier": None},
            "time": "20:00",
        },
    }
    result = answer(CASES["w2-05"], ScriptedClient(plan), search, TABLE, intent="reminder")
    assert result["action"] == CASES["w2-05"]["expected"]["action"]


def test_w1_22_nearest_deadline_reminder_and_its_late_rule():
    plan = {
        "period": "this_week",
        "pick": "nearest",
        "reminder": {"hours_before": 2},
        "rule_question": "What is the late rule?",
    }
    rule = {"abstain": False, "answer": "ECON-101 does not accept late work.", "citations": [1]}
    result = answer(CASES["w1-22"], ScriptedClient(plan, rule), search, TABLE, intent="lookup")
    want = CASES["w1-22"]["expected"]
    same_rows(result, "w1-22")
    assert result["action"] == want["action"]
    assert want["sources"][0] in result["sources"]


def test_w2_14_another_students_list_is_refused():
    result = answer(CASES["w2-14"], ScriptedClient({"other_student": True}), search, TABLE, intent="lookup")
    assert result["abstain"] is True and result["deadlines"] == []


def test_w2_17_other_chat_is_declined_without_a_model_call():
    client = ScriptedClient()
    result = answer(CASES["w2-17"], client, search, TABLE, intent="other")
    assert result["abstain"] is True and client.calls == []


# run_case ------------------------------------------------------------------------------------------------------


def test_run_case_returns_every_graded_field():
    cls = {"intent": "deadline_message", "course": "MATH-212", "urgency": "normal", "multi_step": False}
    ext = {
        "deadlines": [
            item(
                course="MATH-212",
                item="Problem Set 5",
                item_key="ps5",
                date={"kind": "weekday", "weekday": "Pazartesi", "modifier": "next_week"},
                time="23:59",
            )
        ]
    }
    out = run_case(CASES["w2-09"], ScriptedClient(cls, ext), search, TABLE)
    graded = [
        "intent",
        "deadlines",
        "ask_user",
        "abstain",
        "sources",
        "action",
        "count",
        "untrusted_flag",
        "answer_language",
    ]
    assert {k: out[k] for k in graded} == {k: CASES["w2-09"]["expected"][k] for k in graded}
    assert [t["step"] for t in out["trace"]] == ["classifier", "extract"]


def test_run_case_email_with_no_deadline_makes_one_call():
    cls = {"intent": "other", "course": "CS-310", "urgency": "normal", "multi_step": False}
    client = ScriptedClient(cls)
    out = run_case(CASES["w1-04"], client, search, TABLE)
    assert out["deadlines"] == [] and out["abstain"] is False and len(client.calls) == 1


def nearest_case(received_at):
    return {
        "id": "t-nearest",
        "channel": "chat",
        "received_at": received_at,
        "course": None,
        "sender": "user",
        "text": "What is my nearest deadline?",
    }


def test_nearest_asks_when_an_unclear_candidate_comes_first():
    # 12 Nov 18:00: Lab Report 3 is 13 or 20 Nov 23:59; the nearest certain row is ECON-101 Ödev 2, 13 Nov 23:59.
    # Its early candidate is at the same moment, so it may be the nearest one: ask.
    result = answer(
        nearest_case("2026-11-12T18:00:00+03:00"), ScriptedClient({"pick": "nearest"}), search, TABLE, intent="lookup"
    )
    assert result["ask_user"] is True


def test_nearest_does_not_ask_when_both_candidates_come_after_it():
    # 10 Nov 12:00: Quiz 3 on 12 Nov 10:40 comes before both readings of Lab Report 3.
    result = answer(
        nearest_case("2026-11-10T12:00:00+03:00"), ScriptedClient({"pick": "nearest"}), search, TABLE, intent="lookup"
    )
    assert result["ask_user"] is False


def test_nearest_with_only_unclear_rows_asks():
    table = DeadlineTable([r for r in TABLE.rows if r["item_key"] == "labreport3"])
    result = answer(
        nearest_case("2026-11-12T18:00:00+03:00"), ScriptedClient({"pick": "nearest"}), search, table, intent="lookup"
    )
    assert result["ask_user"] is True


def test_a_full_list_still_does_not_ask_when_both_readings_are_ahead():
    result = answer(
        nearest_case("2026-11-12T18:00:00+03:00"), ScriptedClient({"pick": "all"}), search, TABLE, intent="lookup"
    )
    assert result["ask_user"] is False
