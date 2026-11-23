"""The week-3 scoreboard script, built from the committed results folders; no model call."""

import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


w3 = _module("write_week3_scoreboard")
w2 = _module("write_week2_scoreboard")


def _week2_tag_board() -> dict:
    try:
        text = subprocess.run(
            ["git", "show", "week-2:eval/scoreboard.json"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("week-2 tag not available")
    return json.loads(text)


def _week2_board() -> dict:
    return {
        "week": 2,
        "spend_week_usd": w3.WEEK2_SPEND_WEEK_USD,
        "spend_total_usd": w3.WEEK2_SPEND_TOTAL_USD,
        "injection_success": copy.deepcopy(w3.WEEK2_INJECTION_SUCCESS),
    }


def _faithfulness(**unsupported) -> dict:
    entry = {"source": "judge", "k": 1, "n": 13, "value": 0.0769, "ci95_wilson": [0.0137, 0.3331], **unsupported}
    conditions = f"answers from {w3.rel(w3.E2E_RUN)}, labels ..."
    return {
        "for_reporting": True,
        "not_for_reporting_reasons": [],
        "conditions": conditions,
        "unsupported_claims": entry,
    }


def test_build_from_the_real_results_folders():
    board, notes = w3.build(_week2_board(), None)
    assert board["week"] == 3 and board["test_set_size"] == 42
    assert board["e2e_accuracy"] == {"value": 0.905, "ci95": [0.779, 0.962], "n": 42, "script": "eval/run_e2e.py"}
    assert board["abstention_correct"] == {"value": 0.833, "ci95": [0.436, 0.97], "n": 6, "script": "eval/run_e2e.py"}
    assert board["hit_at_5"] == {"value": 0.967, "ci95": [0.833, 0.994], "n": 30, "script": "eval/retrieval.py"}
    assert board["mrr"] == {"value": 0.933, "ci95": [0.85, 1.0], "n": 30, "script": "eval/retrieval.py"}
    assert board["unsupported_claims"] is None and "does not exist yet" in notes[0]
    assert board["task_success"] is None and board["pass_k"] is None
    run_b = json.loads((w3.E2E_RUN / "summary.json").read_text(encoding="utf-8"))
    assert board["cost_per_task_usd"] == run_b["cost_per_case_usd_at_list_price"]
    assert board["latency_p50_s"] == run_b["latency_p50_s"]
    assert board["spend_week_usd"] == run_b["spend_usd"]
    assert board["spend_total_usd"] == round(w3.WEEK2_SPEND_TOTAL_USD + run_b["spend_usd"], 6)


def test_injection_is_carried_from_week_2_and_says_so():
    board, _ = w3.build(_week2_board(), None)
    entry = board["injection_success"]
    assert entry["note"] == "carried from week 2 (W2.8, stub search); not re-measured with real search"
    assert entry["measured_in_week"] == 2
    assert {k: entry[k] for k in ("value", "ci95", "n", "script")} == w3.WEEK2_INJECTION_SUCCESS


def test_week2_constants_match_the_week2_tag():
    tag = _week2_tag_board()
    assert tag["week"] == 2
    assert w3.WEEK2_SPEND_TOTAL_USD == tag["spend_total_usd"]
    assert w3.WEEK2_SPEND_WEEK_USD == tag["spend_week_usd"]
    assert w3.WEEK2_INJECTION_SUCCESS == tag["injection_success"]


def test_rerun_on_a_week3_board_gives_the_same_board():
    first, _ = w3.build(_week2_board(), None)
    again, _ = w3.build(first, None)
    assert again == first


def test_previous_board_of_another_week_is_refused():
    with pytest.raises(ValueError):
        w3.build({"week": 1, "spend_total_usd": 0.0}, None)
    with pytest.raises(ValueError):
        w3.build(None, None)


def test_unsupported_claims_entry_from_the_faithfulness_summary():
    board, notes = w3.build(_week2_board(), _faithfulness())
    assert board["unsupported_claims"] == {
        "value": 0.077,
        "ci95": [0.014, 0.333],
        "n": 13,
        "script": "eval/faithfulness.py",
        "source": "judge",
    }
    assert notes == []
    human, _ = w3.build(_week2_board(), _faithfulness(source="human"))
    assert human["unsupported_claims"]["source"] == "human"


def test_faithfulness_null_value_and_refusal():
    board, notes = w3.build(_week2_board(), _faithfulness(k=0, n=0, value=None, ci95_wilson=None))
    assert board["unsupported_claims"] is None and "null" in notes[0]
    dirty = {**_faithfulness(), "for_reporting": False, "not_for_reporting_reasons": ["judge run did not finish"]}
    with pytest.raises(ValueError, match="judge run did not finish"):
        w3.build(_week2_board(), dirty)


def test_faithfulness_from_another_run_is_refused():
    other = {**_faithfulness(), "conditions": "answers from results/2026-11-22_e2e_other, labels ..."}
    with pytest.raises(ValueError, match="not from"):
        w3.build(_week2_board(), other)


def test_week2_board_without_injection_is_refused():
    with pytest.raises(ValueError, match="injection_success"):
        w3.build({**_week2_board(), "injection_success": None}, None)


def test_unreportable_retrieval_summary_is_refused():
    with pytest.raises(ValueError, match="dirty"):
        w3.retrieval_entries({"reportable": False, "problems": ["dirty"], "overall": {}})


def _paths(monkeypatch, tmp_path, faithfulness: Path) -> Path:
    board = tmp_path / "scoreboard.json"
    board.write_text(json.dumps(_week2_board()), encoding="utf-8")
    monkeypatch.setattr(w3, "BOARD_PATH", board)
    monkeypatch.setattr(w3, "FAITHFULNESS_SUMMARY", faithfulness)
    return board


def test_preview_does_not_write(monkeypatch, tmp_path, capsys):
    board = _paths(monkeypatch, tmp_path, tmp_path / "missing" / "summary.json")
    before = board.read_bytes()
    assert w3.main(["--preview"]) == 0
    assert board.read_bytes() == before
    out = capsys.readouterr().out
    assert '"week": 3' in out and "nothing written" in out


def test_missing_faithfulness_summary_stops_and_names_the_file(monkeypatch, tmp_path, capsys):
    missing = tmp_path / "missing" / "summary.json"
    board = _paths(monkeypatch, tmp_path, missing)
    before = board.read_bytes()
    assert w3.main([]) == 1
    assert str(missing) in capsys.readouterr().err
    assert board.read_bytes() == before


def test_write_with_a_faithfulness_summary(monkeypatch, tmp_path):
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps(_faithfulness()), encoding="utf-8")
    board = _paths(monkeypatch, tmp_path, summary)
    assert w3.main([]) == 0
    written = json.loads(board.read_text(encoding="utf-8"))
    assert written["week"] == 3 and written["unsupported_claims"]["n"] == 13


def test_week2_board_unchanged_by_the_week_keyword():
    tag = _week2_tag_board()
    assert w2.build(tag) == tag
