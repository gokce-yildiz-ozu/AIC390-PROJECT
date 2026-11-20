"""The student's deadline table (docs/data_inventory.md §2), read as it stood at a given time.

A moved deadline is a new row with a later `created_at`; the current row of an item is the newest one created
before the time asked for. Look-ups, counts and reminders are computed here in code, never by the model.
The seed (`data/db/deadlines_seed.jsonl`) holds the rows the test-set messages create, in time order, plus the
syllabus rows that appear in no message (CS-301 Homework 3, CS-310 Lab 3). It belongs to the single synthetic
student of the persona; tools never return another student's rows.
"""

import json
from datetime import datetime, time
from pathlib import Path

from aic390.dates import ISTANBUL, week_range

SEED = Path(__file__).resolve().parents[3] / "data" / "db" / "deadlines_seed.jsonl"

ROW_FIELDS = ["course", "item", "item_key", "due_date", "due_time", "due_candidates", "status", "supersedes"]


def _when(received_at: str) -> datetime:
    return datetime.fromisoformat(received_at).astimezone(ISTANBUL)


def _dates_of(row: dict) -> list[tuple[str, str | None]]:
    if row["due_date"]:
        return [(row["due_date"], row["due_time"])]
    return [(c["date"], c["time"]) for c in row["due_candidates"]]


def _moment(day: str, clock: str | None) -> datetime:
    """A deadline without a time counts until the end of its day."""
    return datetime.combine(
        datetime.fromisoformat(day).date(), time.fromisoformat(clock) if clock else time(23, 59), tzinfo=ISTANBUL
    )


class DeadlineTable:
    def __init__(self, rows: list[dict]):
        self.rows = sorted(rows, key=lambda r: r["created_at"])

    @classmethod
    def seed(cls, path: Path = SEED) -> "DeadlineTable":
        return cls([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])

    def current(self, received_at: str) -> list[dict]:
        """The newest row per (course, item_key) created strictly before received_at."""
        now = _when(received_at)
        latest = {}
        for row in self.rows:
            if _when(row["created_at"]) < now:
                latest[(row["course"], row["item_key"])] = row
        return list(latest.values())

    def find(self, received_at: str, course: str, item_key: str) -> dict | None:
        for row in self.current(received_at):
            if row["course"] == course and row["item_key"] == item_key:
                return row
        return None

    def upcoming(
        self,
        received_at: str,
        course: str | None = None,
        item_keys: list[str] | None = None,
        item_type: str | None = None,
        period: str = "upcoming",
    ) -> list[dict]:
        """Rows still ahead at received_at, filtered. A row with two candidate dates counts if either one fits."""
        out = []
        for row in self.current(received_at):
            if course and row["course"] != course:
                continue
            if item_keys and row["item_key"] not in item_keys:
                continue
            if item_type and row["type"] != item_type:
                continue
            if fitting_dates(row, received_at, period):
                out.append(row)
        return sorted(out, key=lambda r: min(_moment(d, t) for d, t in _dates_of(r)))


def fitting_dates(row: dict, received_at: str, period: str = "upcoming") -> list[tuple[str, str | None]]:
    """The row's dates (one, or its candidates) that are still ahead and inside the period."""
    now = _when(received_at)
    dates = [(d, t) for d, t in _dates_of(row) if _moment(d, t) >= now]
    if period in ("this_week", "next_week"):
        start, end = week_range(received_at, "this" if period == "this_week" else "next")
        dates = [(d, t) for d, t in dates if start.isoformat() <= d <= end.isoformat()]
    return dates


def needs_asking(row: dict, received_at: str, period: str = "upcoming", nearest: dict | None = None) -> bool:
    """Two readings matter only if they change the answer.

    A list or a count: one candidate fits the request and the other does not. "How many are left?" counts
    Lab Report 3 either way (w1-15); "what is due this week?" does not (w1-14).
    The nearest deadline (pick = "nearest"): an unclear row also matters if one of its candidates comes before the
    chosen row or at the same moment, because then it may be the nearest one (w1-22). `nearest` is the chosen row,
    or {} when nothing certain was found.
    """
    if row["due_date"]:
        return False
    fitting = fitting_dates(row, received_at, period)
    if len(fitting) != len(row["due_candidates"]):
        return True
    if nearest is None:
        return False
    if not nearest:
        return bool(fitting)
    chosen = _moment(nearest["due_date"], nearest["due_time"])
    return any(_moment(d, t) <= chosen for d, t in fitting)


def as_listed(row: dict) -> dict:
    """A row as a look-up returns it (interface 5): what is on the list now, so status "new" and no supersedes."""
    return {
        "course": row["course"],
        "item": row["item"],
        "item_key": row["item_key"],
        "due_date": row["due_date"],
        "due_time": row["due_time"],
        "due_candidates": list(row["due_candidates"]),
        "status": "new",
        "supersedes": None,
    }
