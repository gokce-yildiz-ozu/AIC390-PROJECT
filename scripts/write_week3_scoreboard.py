"""Write the week-3 scoreboard from runs that already exist; no model call.

e2e_accuracy, abstention_correct, cost and latency come from Run B (W3.4: real search, answer_v2, the 42 frozen
cases), the only 42-case run with real search; answer_v1 stays the default prompt. hit_at_5 and mrr come from the
W3.5 retrieval baseline. unsupported_claims comes from the W3.6 faithfulness summary (`eval/faithfulness.py kappa`).
injection_success is carried from the week-2 board (W2.8, stub search) and marked as not re-measured.
task_success and pass_k stay null (weeks 4 and 6).

    python scripts/write_week3_scoreboard.py             # writes eval/scoreboard.json
    python scripts/write_week3_scoreboard.py --preview   # prints the board, writes nothing
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
from run_e2e import scoreboard_from  # noqa: E402

from aic390.scoreboard import DEFAULT_PATH, validate, write  # noqa: E402

WEEK = 3
BOARD_PATH = ROOT / DEFAULT_PATH
E2E_RUN = ROOT / "results" / "2026-11-23_e2e_w3-real-ansv2_openai-gpt-oss-120b"
RETRIEVAL_RUN = ROOT / "results" / "2026-11-23_retrieval_hybrid-rerank"
FAITHFULNESS_SUMMARY = ROOT / "results" / "2026-11-23_faithfulness-v1" / "summary.json"

# From `git show week-2:eval/scoreboard.json`. Used when the board on disk is already week 3 (a rerun), so a
# rerun gives the same file.
WEEK2_SPEND_TOTAL_USD = 0.0
WEEK2_SPEND_WEEK_USD = 0.0
WEEK2_INJECTION_SUCCESS = {
    "value": 0.0,
    "ci95": [0.0, 0.562],
    "n": 3,
    "script": "scripts/run_injection_tests.py",
}
INJECTION_NOTE = "carried from week 2 (W2.8, stub search); not re-measured with real search"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def week2_values(previous: dict | None) -> dict:
    """spend_total_usd and injection_success as the week-2 board has them."""
    week = None if previous is None else previous.get("week")
    if week == 2:
        values = {
            "week": 2,
            "spend_week_usd": previous["spend_week_usd"],
            "spend_total_usd": previous["spend_total_usd"],
            "injection_success": previous["injection_success"],
        }
        if values["injection_success"] is None:
            raise ValueError("the week-2 board has no injection_success to carry")
        return values
    if week == WEEK:
        return {
            "week": 2,
            "spend_week_usd": WEEK2_SPEND_WEEK_USD,
            "spend_total_usd": WEEK2_SPEND_TOTAL_USD,
            "injection_success": WEEK2_INJECTION_SUCCESS,
        }
    raise ValueError(f"previous board is week {week}; expected the week-2 board (or week 3 on a rerun)")


def _ci(pair: list[float]) -> list[float]:
    return [round(x, 3) for x in pair]


def retrieval_entries(summary: dict) -> dict:
    if not summary["reportable"]:
        raise ValueError("refusing the retrieval summary: " + "; ".join(summary.get("problems") or []))
    overall = summary["overall"]
    hit, mrr = overall["hit_at_5"], overall["mrr"]
    return {
        "hit_at_5": {
            "value": round(hit["value"], 3),
            "ci95": _ci(hit["ci95_wilson"]),
            "n": hit["n"],
            "script": "eval/retrieval.py",
        },
        "mrr": {
            "value": round(mrr["value"], 3),
            "ci95": _ci(mrr["ci95_bootstrap"]),
            "n": overall["n"],
            "script": "eval/retrieval.py",
        },
    }


def unsupported_entry(summary: dict) -> tuple[dict | None, str | None]:
    """The scoreboard entry, or None and the reason it is null."""
    reasons = summary.get("not_for_reporting_reasons") or []
    if reasons:
        raise ValueError("refusing the faithfulness summary: " + "; ".join(reasons))
    if rel(E2E_RUN) not in (summary.get("conditions") or ""):
        raise ValueError(f"refusing the faithfulness summary: its answers are not from {rel(E2E_RUN)}")
    u = summary["unsupported_claims"]
    if u.get("value") is None:
        return None, (
            f"unsupported_claims is null: the faithfulness summary ({u.get('source')}) has no value (n = {u.get('n')})"
        )
    entry = {
        "value": round(u["value"], 3),
        "ci95": _ci(u["ci95_wilson"]),
        "n": u["n"],
        "script": "eval/faithfulness.py",
        "source": u["source"],
    }
    return entry, None


def build(previous: dict | None, faithfulness: dict | None) -> tuple[dict, list[str]]:
    """The week-3 board and the notes to print about null keys."""
    base = week2_values(previous)
    board = scoreboard_from(load(E2E_RUN / "summary.json"), load(E2E_RUN / "config.json"), base, week=WEEK)
    board.update(retrieval_entries(load(RETRIEVAL_RUN / "summary.json")))
    notes = []
    if faithfulness is None:
        notes.append(f"unsupported_claims is null: {rel(FAITHFULNESS_SUMMARY)} does not exist yet")
    else:
        board["unsupported_claims"], why = unsupported_entry(faithfulness)
        if why:
            notes.append(why)
    board["injection_success"] = {**base["injection_success"], "note": INJECTION_NOTE, "measured_in_week": 2}
    problems = validate(board)
    if problems:
        raise ValueError("; ".join(problems))
    return board, notes


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", action="store_true", help="print the board, do not write eval/scoreboard.json")
    args = ap.parse_args(argv)

    if not FAITHFULNESS_SUMMARY.exists() and not args.preview:
        print(
            f"error: {rel(FAITHFULNESS_SUMMARY)} is missing; run `python eval/faithfulness.py run`, then `kappa`, "
            "or use --preview",
            file=sys.stderr,
        )
        return 1
    faithfulness = load(FAITHFULNESS_SUMMARY) if FAITHFULNESS_SUMMARY.exists() else None
    previous = load(BOARD_PATH) if BOARD_PATH.exists() else None
    try:
        board, notes = build(previous, faithfulness)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not args.preview:
        write(board, BOARD_PATH)
    print(json.dumps(board, indent=2))
    for note in notes:
        print(note)
    print("preview only, nothing written" if args.preview else f"wrote {rel(BOARD_PATH)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
