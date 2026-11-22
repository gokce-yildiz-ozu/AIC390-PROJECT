"""Write the week-2 scoreboard from runs that already exist; no model call.

e2e_accuracy, abstention_correct, cost and latency come from the first run of the W2.5 winner (extract_v1, the
42 frozen cases, stub search, seed table). injection_success comes from the W2.8 run after the course check, with
the v1 prompts (the setting the winner uses). Every other key stays null.

    python scripts/write_week2_scoreboard.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
from run_e2e import scoreboard_from  # noqa: E402

from aic390.scoreboard import DEFAULT_PATH, write  # noqa: E402
from aic390.stats import proportion_ci  # noqa: E402

E2E_RUN = ROOT / "results" / "2026-11-22_e2e_w25-v1-a_openai-gpt-oss-120b"
INJECTION_RUN = ROOT / "results" / "2026-11-22_injection_after-course-check_openai-gpt-oss-120b"
INJECTION_SETTING = "v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def injection_entry(summary: dict, setting: str) -> dict:
    counts = summary["by_setting"][setting]
    broke, n = counts["n"] - counts["held"], counts["n"]
    low, high = proportion_ci(broke, n, method="wilson")
    return {
        "value": round(broke / n, 3),
        "ci95": [round(low, 3), round(high, 3)],
        "n": n,
        "script": "scripts/run_injection_tests.py",
    }


def build(previous: dict | None) -> dict:
    board = scoreboard_from(load(E2E_RUN / "summary.json"), load(E2E_RUN / "config.json"), previous)
    board["injection_success"] = injection_entry(load(INJECTION_RUN / "summary.json"), INJECTION_SETTING)
    return board


def main() -> None:
    previous = load(DEFAULT_PATH) if DEFAULT_PATH.exists() else None
    board = build(previous)
    write(board)
    print(json.dumps(board, indent=2))


if __name__ == "__main__":
    main()
