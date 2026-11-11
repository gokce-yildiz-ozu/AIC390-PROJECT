"""The one scoreboard every week's report pastes (handbook section 5)."""

import json
from pathlib import Path

ACCURACY_KEYS = (
    "e2e_accuracy",
    "abstention_correct",
    "unsupported_claims",
    "hit_at_5",
    "mrr",
    "task_success",
    "pass_k",
    "injection_success",
)
SCALAR_KEYS = ("cost_per_task_usd", "latency_p50_s", "spend_week_usd", "spend_total_usd")
DEFAULT_PATH = Path("eval/scoreboard.json")


def empty_scoreboard(week: int, test_set_size: int | None = None) -> dict:
    board: dict = {"week": week, "test_set_size": test_set_size}
    board.update({k: None for k in ACCURACY_KEYS + SCALAR_KEYS})
    return board


def validate(board: dict) -> list[str]:
    problems = []
    for key in ("week", "test_set_size", *ACCURACY_KEYS, *SCALAR_KEYS):
        if key not in board:
            problems.append(f"missing key: {key}")
    for key in ACCURACY_KEYS:
        entry = board.get(key)
        if entry is None:
            continue
        for field in ("value", "n", "script"):
            if field not in entry:
                problems.append(f"{key}: missing {field}")
    return problems


def write(board: dict, path: Path = DEFAULT_PATH) -> None:
    problems = validate(board)
    if problems:
        raise ValueError("; ".join(problems))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
