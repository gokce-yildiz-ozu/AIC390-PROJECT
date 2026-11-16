import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aic390.cost import request_cost
from aic390.llm import FakeClient
from aic390.scoreboard import empty_scoreboard, validate

ROOT = Path(__file__).resolve().parents[1]
WEEK1 = ROOT / "eval/testsets/week1_inputs.jsonl"
sys.path.insert(0, str(ROOT / "scripts"))
import run_baseline  # noqa: E402


class RecordingClient(FakeClient):
    def __init__(self, fail_on_call: int | None = None):
        super().__init__()
        self.calls: list[list[dict]] = []
        self.fail_on_call = fail_on_call

    def chat(self, messages, temperature):
        self.calls.append(messages)
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            raise RuntimeError("simulated crash")
        return super().chat(messages, temperature)


def test_run_covers_every_input_at_every_temperature():
    inputs = [{"id": "a", "text": "hi"}, {"id": "b", "text": "there"}]
    records = run_baseline.run(FakeClient(), inputs, "system", [0.0, 0.7, 1.2], prices=None)
    assert len(records) == 6
    assert {(r["id"], r["temperature"]) for r in records} == {(i, t) for i in "ab" for t in (0.0, 0.7, 1.2)}
    assert run_baseline.summarize(records)["failed"] == 0


def test_user_message_has_header_and_no_labels():
    row = run_baseline.load_inputs(WEEK1)[1]  # w1-02, "next Friday"
    client = RecordingClient()
    run_baseline.run(client, [row], "system", [0.0], prices=None)
    user = client.calls[0][-1]["content"]
    assert f"received_at: {row['received_at']}" in user
    assert f"sender: {row['sender']}" in user
    assert f"course: {row['course']}" in user
    assert "channel: email" in user
    assert user.endswith(row["text"])
    assert row["expected"] not in user
    assert "ingredients" not in user and "relative-date" not in user


def test_null_course_is_written_as_none():
    msg = run_baseline.build_user_message({"id": "x", "text": "t", "course": None})
    assert "course: none" in msg


def test_missing_price_gives_null_cost_and_one_warning(capsys):
    inputs = [{"id": "a", "text": "hi"}, {"id": "b", "text": "there"}]
    records = run_baseline.run(FakeClient(), inputs, "system", [0.0, 1.2], prices={})
    assert all(r["cost_usd"] is None for r in records)
    assert capsys.readouterr().err.count("warning: no price") == 1
    summary = run_baseline.summarize(records)
    assert summary["cost_usd_at_list_price"] is None
    assert summary["usd_per_1000_requests"] is None


def test_known_price_uses_configured_model_id():
    prices = {"fake-model": {"input_usd_per_mtok": 1.0, "output_usd_per_mtok": 1.0, "source": "x"}}
    records = run_baseline.run(FakeClient(), [{"id": "a", "text": "hi"}], "s", [0.0], prices=prices)
    assert records[0]["cost_usd"] == pytest.approx((records[0]["input_tokens"] + 12) / 1_000_000)


def test_records_are_streamed_so_a_crash_keeps_partial_results():
    inputs = [{"id": c, "text": c} for c in "abcd"]
    seen = []
    with pytest.raises(RuntimeError):
        run_baseline.run(RecordingClient(fail_on_call=3), inputs, "s", [0.0], prices=None, on_record=seen.append)
    assert [r["id"] for r in seen] == ["a", "b"]


def test_sleep_runs_between_calls_only():
    slept = []
    inputs = [{"id": c, "text": c} for c in "abc"]
    run_baseline.run(FakeClient(), inputs, "s", [0.0, 0.7], prices=None, sleep_s=5, sleep=slept.append)
    assert slept == [5] * 5


def test_select_inputs_by_ids_and_limit():
    rows = run_baseline.load_inputs(WEEK1)
    picked = run_baseline.select_inputs(rows, ["w1-22", "w1-01", "w1-12"], None)
    assert [r["id"] for r in picked] == ["w1-22", "w1-01", "w1-12"]
    assert len(run_baseline.select_inputs(rows, None, 3)) == 3
    with pytest.raises(ValueError):
        run_baseline.select_inputs(rows, ["w1-99"], None)


def test_compare_temperatures():
    def rec(i, t, text, error=None):
        return {"id": i, "temperature": t, "text": text, "error": error}

    records = [
        rec("a", 0, "x"), rec("a", 1, "x"),
        rec("b", 0, "x"), rec("b", 1, "y"),
        rec("c", 0, "x"), rec("c", 1, "", "boom"),
    ]  # fmt: skip
    status = run_baseline.compare_temperatures(records, [0, 1])
    assert status == {"a": "identical", "b": "differ (2 distinct / 2)", "c": "incomplete"}


def test_git_dirty_files_sees_only_tracked_code_changes(tmp_path):
    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                       cwd=tmp_path, check=True, capture_output=True)  # fmt: skip

    git("init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/a.py").write_text("x = 1\n")
    (tmp_path / "notes.md").write_text("n\n")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    assert run_baseline.git_dirty_files(cwd=tmp_path) == []

    (tmp_path / "notes.md").write_text("changed outside the code paths\n")
    (tmp_path / "src/new.py").write_text("untracked\n")
    assert run_baseline.git_dirty_files(cwd=tmp_path) == []

    (tmp_path / "src/a.py").write_text("x = 2\n")
    assert run_baseline.git_dirty_files(cwd=tmp_path) == ["src/a.py"]


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
    cmd = [sys.executable, "scripts/run_baseline.py", "--dry-run", "--inputs", str(WEEK1), "--out", str(out)]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr

    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    assert config["model"] == "fake-model"
    assert config["prompt"].endswith("baseline_v1.md")
    assert config["temperatures"] == [0.0, 0.7, 1.2]
    assert config["commit"]
    assert isinstance(config["dirty"], bool)

    lines = (out / "outputs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 75

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["succeeded"] == summary["requests"] == 75

    with (out / "grading.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0].keys()) == run_baseline.GRADING_COLUMNS
    assert len(rows) == 75
    assert all(r["label"] == "" and r["note"] == "" for r in rows)
    assert [r["temperature"] for r in rows[:3]] == ["0.0", "0.7", "1.2"]
    assert rows[0]["expected"].startswith("CS-301")

    # A second run into the same directory must not overwrite the evidence.
    again = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert again.returncode == 1
    assert "already has results" in again.stderr
