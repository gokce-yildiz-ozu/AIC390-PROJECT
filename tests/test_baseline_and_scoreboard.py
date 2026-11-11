import json
import subprocess
import sys
from pathlib import Path

import pytest

from aic390.cost import request_cost
from aic390.llm import FakeClient
from aic390.scoreboard import empty_scoreboard, validate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_baseline  # noqa: E402


def test_run_covers_every_input_at_every_temperature():
    inputs = [{"id": "a", "text": "hi"}, {"id": "b", "text": "there"}]
    records = run_baseline.run(FakeClient(), inputs, "system", [0.0, 0.7, 1.2], prices=None)
    assert len(records) == 6
    assert {(r["id"], r["temperature"]) for r in records} == {(i, t) for i in "ab" for t in (0.0, 0.7, 1.2)}
    assert run_baseline.summarize(records)["failed"] == 0


def test_cost_uses_per_million_prices_and_refuses_unknown_models():
    prices = {"m": {"input_usd_per_mtok": 1.0, "output_usd_per_mtok": 4.0}}
    assert request_cost("m", 1_000_000, 500_000, prices) == pytest.approx(3.0)
    with pytest.raises(KeyError):
        request_cost("other", 1, 1, prices)


def test_committed_scoreboard_is_valid():
    board = json.loads((ROOT / "eval/scoreboard.json").read_text(encoding="utf-8"))
    assert validate(board) == []
    assert validate(empty_scoreboard(1)) == []


def test_dry_run_end_to_end(tmp_path):
    out = tmp_path / "run"
    proc = subprocess.run(
        [sys.executable, "scripts/run_baseline.py", "--dry-run", "--out", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["succeeded"] == summary["requests"] > 0
