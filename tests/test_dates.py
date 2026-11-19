"""Every expected date below comes from eval/testsets/week2_cases.jsonl (the case id is in the test name)."""

import pytest

from aic390.dates import DateError, remind_at, resolve, week_range


def test_w1_01_absolute_date_with_time():
    out = resolve({"kind": "absolute", "day": 20, "month": 11, "year": 2026}, "23:59", "2026-11-09T09:10:00+03:00")
    assert out == {"due_date": "2026-11-20", "due_time": "23:59", "due_candidates": [], "ask_user": False}


def test_w1_02_next_friday_from_saturday_gives_two_candidates():
    out = resolve({"kind": "weekday", "weekday": "friday", "modifier": "next"}, "23:59", "2026-11-07T18:30:00+03:00")
    assert out["due_date"] is None and out["ask_user"] is True
    assert out["due_candidates"] == [{"date": "2026-11-13", "time": "23:59"}, {"date": "2026-11-20", "time": "23:59"}]


def test_w1_05_following_monday_after_the_original_date_keeps_the_time():
    out = resolve(
        {"kind": "weekday_after_base", "weekday": "monday"},
        "same",
        "2026-11-10T16:20:00+03:00",
        base_date="2026-11-20",
        base_time="23:59",
    )
    assert (out["due_date"], out["due_time"]) == ("2026-11-23", "23:59")


def test_w1_06_extended_by_one_week_from_the_retrieved_date():
    out = resolve(
        {"kind": "shift", "days": 7}, "same", "2026-11-11T13:05:00+03:00", base_date="2026-11-13", base_time="23:59"
    )
    assert (out["due_date"], out["due_time"]) == ("2026-11-20", "23:59")


def test_w1_07_turkish_weekday_sent_on_wednesday_is_unambiguous():
    out = resolve({"kind": "weekday", "weekday": "Cuma", "modifier": None}, "23:59", "2026-11-11T17:40:00+03:00")
    assert (out["due_date"], out["ask_user"]) == ("2026-11-13", False)


def test_w2_09_haftaya_pazartesi_sent_on_wednesday_is_one_date():
    out = resolve(
        {"kind": "weekday", "weekday": "Pazartesi", "modifier": "next_week"}, "23:59", "2026-11-18T09:30:00+03:00"
    )
    assert out == {"due_date": "2026-11-23", "due_time": "23:59", "due_candidates": [], "ask_user": False}


def test_next_week_sent_on_the_same_weekday_is_seven_days_later():
    out = resolve({"kind": "weekday", "weekday": "friday", "modifier": "next_week"}, None, "2026-11-13T09:00:00+03:00")
    assert out["due_date"] == "2026-11-20"


def test_weekday_sent_on_the_same_weekday_asks_the_user():
    out = resolve({"kind": "weekday", "weekday": "friday", "modifier": None}, None, "2026-11-13T09:00:00+03:00")
    assert [c["date"] for c in out["due_candidates"]] == ["2026-11-13", "2026-11-20"]


def test_w1_08_day_before_the_make_up_week_and_no_time():
    out = resolve({"kind": "shift", "days": -1}, None, "2026-11-12T10:00:00+03:00", base_date="2026-11-30")
    assert (out["due_date"], out["due_time"]) == ("2026-11-29", None)


def test_w1_23_turkish_absolute_date():
    out = resolve({"kind": "absolute", "day": 16, "month": 11, "year": None}, "23:59", "2026-11-13T17:30:00+03:00")
    assert out["due_date"] == "2026-11-16"


def test_date_without_year_in_january_sent_in_november_is_next_year():
    out = resolve({"kind": "absolute", "day": 12, "month": 1, "year": None}, None, "2026-11-13T17:30:00+03:00")
    assert out["due_date"] == "2027-01-12"


def test_w1_14_this_week_and_w1_18_next_week():
    assert [d.isoformat() for d in week_range("2026-11-13T12:00:00+03:00")] == ["2026-11-09", "2026-11-15"]
    assert [d.isoformat() for d in week_range("2026-11-13T14:10:00+03:00", "next")] == ["2026-11-16", "2026-11-22"]


def test_w1_17_reminder_is_due_minus_24_hours():
    assert remind_at("2026-11-23", "23:59") == "2026-11-22T23:59:00+03:00"


def test_w1_22_reminder_two_hours_before():
    assert remind_at("2026-11-13", "23:59", hours_before=2) == "2026-11-13T21:59:00+03:00"


@pytest.mark.parametrize(
    "expr",
    [
        {"kind": "shift", "days": 7},
        {"kind": "weekday", "weekday": "someday"},
        {"kind": "weekday", "weekday": "friday", "modifier": "soonish"},
        {"kind": "absolute", "day": 31, "month": 11},
        {"kind": "tomorrow-ish"},
    ],
)
def test_unresolvable_expressions_raise_instead_of_guessing(expr):
    with pytest.raises(DateError):
        resolve(expr, None, "2026-11-13T12:00:00+03:00")


def test_bad_time_raises():
    with pytest.raises(DateError):
        resolve({"kind": "absolute", "day": 1, "month": 12}, "late evening", "2026-11-13T12:00:00+03:00")
