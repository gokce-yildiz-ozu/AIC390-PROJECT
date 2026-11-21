"""Date resolution in code: the model extracts a date expression, this module turns it into dates (P1, W1).

The model never does date arithmetic. It returns one of the expressions below; `resolve` computes the date
against the message's received_at. Two readings consistent with the expression give two candidates and
`ask_user`; the labelling rules are in eval/testsets/README.md.

Expressions (JSON from the extraction step):
    {"kind": "absolute", "day": 20, "month": 11, "year": 2026}      year may be null
    {"kind": "weekday", "weekday": "friday", "modifier": null}       "Friday", "Cuma"
    {"kind": "weekday", "weekday": "friday", "modifier": "next"}     "next Friday" (two readings)
    {"kind": "weekday", "weekday": "monday", "modifier": "next_week"} "haftaya Pazartesi" (that day of next week)
    {"kind": "weekday_after_base", "weekday": "monday"}              "moved to the following Monday"
    {"kind": "shift", "days": 7}                                     "extended by one week" (needs a base date)
Time: "23:59", "same" (keep the base time) or null (never filled in).
"""

import re
from datetime import date, datetime, time, timedelta, timezone

ISTANBUL = timezone(timedelta(hours=3))  # Türkiye has had no daylight saving time since 2016

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
TURKISH_WEEKDAYS = {
    "pazartesi": "monday",
    "salı": "tuesday",
    "çarşamba": "wednesday",
    "perşembe": "thursday",
    "cuma": "friday",
    "cumartesi": "saturday",
    "pazar": "sunday",
}


MONTHS = {
    **{
        m: i
        for i, m in enumerate(
            [
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            ],
            1,
        )
    },
    **{
        m: i
        for i, m in enumerate(
            [
                "ocak",
                "şubat",
                "mart",
                "nisan",
                "mayıs",
                "haziran",
                "temmuz",
                "ağustos",
                "eylül",
                "ekim",
                "kasım",
                "aralık",
            ],
            1,
        )
    },
}
_MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), ("y", "m", "d")),  # 2026-11-30
    (
        re.compile(rf"\b(\d{{1,2}})\.? ({_MONTH_NAMES}),? (\d{{4}})\b", re.IGNORECASE),
        ("d", "mn", "y"),
    ),  # 30 November 2026
    (
        re.compile(rf"\b({_MONTH_NAMES}) (\d{{1,2}}),? (\d{{4}})\b", re.IGNORECASE),
        ("mn", "d", "y"),
    ),  # November 30, 2026
]


class DateError(ValueError):
    """The expression cannot be resolved; the caller flags the deadline instead of guessing."""


def _month(name: str) -> int:
    """Month number from its name; Turkish capitals fold by Turkish rules ("KASIM" -> "kasım")."""
    plain = name.casefold()
    return MONTHS.get(plain) or MONTHS[name.replace("I", "ı").replace("İ", "i").casefold()]


def find_date(text: str) -> date | None:
    """The first full date written in a document: ISO, or with an English or Turkish month name
    ("2026-11-30", "30 November 2026", "November 30, 2026", "30 Kasım 2026"). None if there is none."""
    found = []
    for pattern, order in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            parts = dict(zip(order, match.groups(), strict=True))
            month = int(parts["m"]) if "m" in parts else _month(parts["mn"])
            try:
                found.append((match.start(), date(int(parts["y"]), month, int(parts["d"]))))
            except ValueError:
                continue
    return min(found)[1] if found else None


def received_date(received_at: str) -> date:
    return datetime.fromisoformat(received_at).astimezone(ISTANBUL).date()


def weekday_index(name: str) -> int:
    key = name.strip().lower()
    key = TURKISH_WEEKDAYS.get(key, key)
    if key not in WEEKDAYS:
        raise DateError(f"unknown weekday {name!r}")
    return WEEKDAYS.index(key)


def next_occurrence(after: date, weekday: int, include_same_day: bool = False) -> date:
    days = (weekday - after.weekday()) % 7
    if days == 0 and not include_same_day:
        days = 7
    return after + timedelta(days=days)


def candidate_dates(expr: dict, received: date, base: date | None = None) -> list[date]:
    kind = expr.get("kind")
    if kind == "absolute":
        year = expr.get("year") or received.year
        try:
            result = date(year, expr["month"], expr["day"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DateError(f"bad absolute date {expr}") from exc
        if expr.get("year") is None and (received - result).days > 180:
            result = result.replace(year=year + 1)  # "12 January" sent in November means next year
        return [result]
    if kind == "weekday":
        target = weekday_index(expr["weekday"])
        modifier = expr.get("modifier")
        if modifier == "next_week":
            # "haftaya Pazartesi": the given day of the calendar week after the received week; one reading.
            monday = received - timedelta(days=received.weekday()) + timedelta(days=7)
            return [monday + timedelta(days=target)]
        if modifier not in (None, "next"):
            raise DateError(f"unknown weekday modifier {modifier!r}")
        if modifier == "next":
            # "next Friday": the coming Friday or the one after it; both are common readings.
            first = next_occurrence(received, target)
            return [first, first + timedelta(days=7)]
        if received.weekday() == target:
            # "Friday" sent on a Friday: today or a week later.
            return [received, received + timedelta(days=7)]
        return [next_occurrence(received, target)]
    if kind == "weekday_after_base":
        if base is None:
            raise DateError("needs the original date")
        return [next_occurrence(base, weekday_index(expr["weekday"]))]
    if kind == "shift":
        if base is None:
            raise DateError("needs the original date")
        return [base + timedelta(days=int(expr["days"]))]
    raise DateError(f"unknown expression kind {kind!r}")


def parse_time(value: str | None, base_time: str | None = None) -> str | None:
    if value is None:
        return None
    if value == "same":
        return base_time
    try:
        return time.fromisoformat(value).strftime("%H:%M")
    except ValueError as exc:
        raise DateError(f"bad time {value!r}") from exc


def resolve(
    expr: dict,
    time_value: str | None,
    received_at: str,
    base_date: str | None = None,
    base_time: str | None = None,
) -> dict:
    """The date fields of one deadline row in the interface 5 output: due_date, due_time, due_candidates, ask_user."""
    base = date.fromisoformat(base_date) if base_date else None
    dates = candidate_dates(expr, received_date(received_at), base)
    due_time = parse_time(time_value, base_time)
    if len(dates) == 1:
        return {"due_date": dates[0].isoformat(), "due_time": due_time, "due_candidates": [], "ask_user": False}
    return {
        "due_date": None,
        "due_time": None,
        "due_candidates": [{"date": d.isoformat(), "time": due_time} for d in dates],
        "ask_user": True,
    }


def week_range(received_at: str, which: str = "this") -> tuple[date, date]:
    """Monday to Sunday of the received week ("this") or the week after it ("next")."""
    day = received_date(received_at)
    monday = day - timedelta(days=day.weekday())
    if which == "next":
        monday += timedelta(days=7)
    return monday, monday + timedelta(days=6)


def remind_at(due_date: str, due_time: str | None, hours_before: float = 24) -> str:
    """Reminder time as ISO 8601 with +03:00. No due time: the end of the due day is used, and the preview says so."""
    clock = time.fromisoformat(due_time) if due_time else time(23, 59)
    due = datetime.combine(date.fromisoformat(due_date), clock, tzinfo=ISTANBUL)
    return (due - timedelta(hours=hours_before)).isoformat()
