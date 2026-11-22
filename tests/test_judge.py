"""Offline tests for the W2.6 judge: fake judge clients and a temporary git repository; no model is called."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aic390.llm import FakeClient, LLMResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import judge  # noqa: E402

CRITERIA = judge.criteria_list(["says A", "says B"], ["does C"])


class ScriptedJudge(FakeClient):
    """Returns the given replies in order; the model id can be changed to test the smoke check."""

    def __init__(self, replies: list[str], model: str = "fake-judge", returned: str | None = None):
        super().__init__(model)
        self.replies = list(replies)
        self.returned = returned or model
        self.calls = 0

    def chat(self, messages: list[dict], temperature: float) -> LLMResponse:
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, LLMResponse):
            return reply
        return LLMResponse(reply, self.returned, 10, 10, 0.0, model_requested=self.model)


def reply(items: list[dict]) -> str:
    return json.dumps({"items": items}, ensure_ascii=False)


def items(met: dict[str, bool]) -> list[dict]:
    return [{**c, "met": met[c["criterion"]], "evidence": ""} for c in CRITERIA]


def judge_one(client) -> dict:
    system, template = judge.load_judge_prompt()
    return judge.judge_answer(client, system, template, "q?", "an answer", ["says A", "says B"], ["does C"])


# Schema and verdict ---------------------------------------------------------------------------------------------


def test_a_missing_criterion_is_rejected():
    with pytest.raises(ValueError, match="missing"):
        judge.parse_reply(reply(items({"says A": True, "says B": True, "does C": False})[:2]), CRITERIA)


def test_a_duplicated_criterion_is_rejected():
    full = items({"says A": True, "says B": True, "does C": False})
    with pytest.raises(ValueError, match="duplicated"):
        judge.parse_reply(reply([*full, full[0]]), CRITERIA)


def test_an_unknown_criterion_or_wrong_type_is_rejected():
    full = items({"says A": True, "says B": True, "does C": False})
    with pytest.raises(ValueError, match="unknown"):
        judge.parse_reply(reply([*full[:2], {**full[2], "type": "must_include"}]), CRITERIA)


def test_a_think_block_before_the_json_is_ignored():
    full = items({"says A": True, "says B": True, "does C": False})
    parsed = judge.parse_reply("<think>{not json}</think>\n" + reply(full), CRITERIA)
    assert [i["met"] for i in parsed] == [True, True, False]


def test_criteria_match_ignoring_case_quotes_spacing_and_a_trailing_period():
    criteria = judge.criteria_list(["ECON-101 geç teslimi kabul etmez"], ["CS-301'in günde %10 kuralını vermek"])
    loose = [
        {"criterion": "econ-101  geç teslimi kabul etmez.", "type": "must_include", "met": True, "evidence": ""},
        {"criterion": "CS-301’in günde %10 kuralını vermek", "type": "must_not", "met": False, "evidence": ""},
    ]
    parsed = judge.parse_reply(reply(loose), criteria)
    assert [i["criterion"] for i in parsed] == [c["criterion"] for c in criteria]  # the original wording is kept
    with pytest.raises(ValueError, match="missing"):
        judge.parse_reply(reply([{**loose[0], "criterion": "ECON-102 geç teslimi kabul etmez"}, loose[1]]), criteria)


def test_pass_is_computed_by_code_and_a_met_must_not_fails():
    client = ScriptedJudge([reply(items({"says A": True, "says B": True, "does C": True}))])
    result = judge_one(client)
    assert result["valid"] is True and result["judge_pass"] is False


def test_every_must_include_met_and_no_must_not_passes():
    result = judge_one(ScriptedJudge([reply(items({"says A": True, "says B": True, "does C": False}))]))
    assert result["judge_pass"] is True
    result = judge_one(ScriptedJudge([reply(items({"says A": True, "says B": False, "does C": False}))]))
    assert result["judge_pass"] is False


def test_one_retry_after_an_invalid_reply():
    good = reply(items({"says A": True, "says B": True, "does C": False}))
    client = ScriptedJudge(["not json", good])
    result = judge_one(client)
    assert client.calls == 2 and result["valid"] and result["judge_pass"] is True


def test_invalid_twice_gives_null_never_a_guess():
    client = ScriptedJudge(["not json", '{"items": []}'])
    result = judge_one(client)
    assert client.calls == 2
    assert result["valid"] is False and result["judge_pass"] is None and result["items"] is None


def test_the_smoke_example_is_the_one_in_the_prompt():
    text = (ROOT / "prompts" / "judge_v1.md").read_text(encoding="utf-8")
    assert judge.SMOKE["question"] in text and judge.SMOKE["answer"] in text
    for c in judge.criteria_list(judge.SMOKE["must_include"], judge.SMOKE["must_not"]):
        assert json.dumps(c, ensure_ascii=False) in text


# Sheet --------------------------------------------------------------------------------------------------------


def test_sheet_writes_20_rows_without_a_model_and_never_overwrites(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(judge, "OpenAICompatibleClient", None)  # any model client would fail
    out = tmp_path / "sheet"
    assert judge.main(["sheet", "--dir", str(out)]) == 0
    assert capsys.readouterr().out.strip() == "20 rows"
    rows = judge.read_sheet(out / judge.LABELS)
    assert len(rows) == 20 and tuple(rows[0].keys()) == judge.COLUMNS
    assert sum(r["source_run"] == judge.BASELINE_RUN for r in rows) == 9
    assert sum(r["source_run"] == judge.V1_RUN for r in rows) == 11
    assert all(r["human_pass"] == "" and r["human_note"] == "" for r in rows)
    assert judge.main(["sheet", "--dir", str(out)]) == 1


def test_the_v1_sample_is_fixed_by_the_seed():
    cases = judge.load_jsonl(judge.CASES)
    assert judge.sample_v1_ids(cases) == judge.sample_v1_ids(cases)
    assert len(set(judge.sample_v1_ids(cases))) == 11


# Blind order ---------------------------------------------------------------------------------------------------


def _labelled_sheet(folder: Path, labels: list[str] | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    rows, _ = judge.build_rows()
    path = folder / judge.LABELS
    judge.write_sheet(rows, path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        sheet = list(csv.DictReader(f))
    labels = labels or ["true" if i % 3 else "false" for i in range(len(sheet))]  # fake labels for the tests
    for row, label in zip(sheet, labels, strict=True):
        row["human_pass"] = label
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=judge.COLUMNS)
        writer.writeheader()
        writer.writerows(sheet)
    return path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    return repo


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A temporary git repository standing in for this one: the sheet must be committed in it, under results/."""
    root = _repo(tmp_path)
    monkeypatch.setattr(judge, "REPO", root)
    monkeypatch.setattr(judge, "RESULTS_DIR", root / "results")
    return root


def _commit(root: Path) -> None:
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "labels")


@pytest.fixture
def no_model(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a model client was created")

    monkeypatch.setattr(judge, "OpenAICompatibleClient", refuse)


def test_run_refuses_an_untracked_sheet(repo, capsys, no_model):
    path = _labelled_sheet(repo / "results" / "2026-11-22_judge-v1")
    assert judge.main(["run", "--dir", str(path.parent)]) == 1
    assert "not committed" in capsys.readouterr().err
    assert not (path.parent / judge.OUTPUTS).exists()


def test_run_refuses_a_sheet_with_uncommitted_changes(repo, capsys, no_model):
    path = _labelled_sheet(repo / "results" / "2026-11-22_judge-v1")
    _commit(repo)
    assert judge.labels_git_state(path)[0] is None
    path.write_bytes(path.read_bytes().replace(b",true,", b",false,", 1))
    assert judge.main(["run", "--dir", str(path.parent)]) == 1
    assert "uncommitted changes" in capsys.readouterr().err


def test_run_refuses_an_empty_human_pass_even_when_committed(repo, capsys, no_model):
    path = _labelled_sheet(repo / "results" / "2026-11-22_judge-v1", ["true"] * 19 + [""])
    _commit(repo)
    assert judge.main(["run", "--dir", str(path.parent)]) == 1
    last_id = judge.read_sheet(path)[19]["id"]
    assert f"human_pass is not true or false in rows: 20 ({last_id})" in capsys.readouterr().err


def test_a_real_run_refuses_a_committed_sheet_outside_results(repo, capsys, no_model):
    # a committed sheet of made-up labels elsewhere must not unlock real verdicts on the real answers
    path = _labelled_sheet(repo / "elsewhere")
    _commit(repo)
    assert judge.main(["run", "--dir", str(path.parent)]) == 1
    assert "under results/" in capsys.readouterr().err


def test_a_sheet_committed_in_another_repository_does_not_count(repo, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q")
    path = _labelled_sheet(other / "judge")
    _commit(other)
    assert "outside the repository" in judge.labels_git_state(path)[0]


def test_run_refuses_a_changed_answer(tmp_path):
    path = _labelled_sheet(tmp_path / "judge")
    sheet = judge.read_sheet(path)
    rows, _ = judge.build_rows()
    sheet[0]["answer"] = "edited"
    assert "answer text changed in rows: " + rows[0]["id"] in judge.label_problems(sheet, rows)


def test_a_semicolon_or_non_utf8_sheet_gets_a_clear_message(tmp_path):
    path = _labelled_sheet(tmp_path / "judge")
    path.write_text("id;source_run\nw1-09;x\n", encoding="cp1254")
    with pytest.raises(ValueError, match="comma separators"):
        judge.read_sheet(path)
    path.write_bytes("id,source_run\nçğı,x\n".encode("cp1254"))
    with pytest.raises(ValueError, match="UTF-8"):
        judge.read_sheet(path)


def test_a_dry_run_inside_results_is_refused(tmp_path, monkeypatch):
    results = tmp_path / "results"
    monkeypatch.setattr(judge, "RESULTS_DIR", results)
    path = _labelled_sheet(results / "2026-11-22_judge-v1")
    assert judge.main(["run", "--dry-run", "--dir", str(path.parent)]) == 1


def test_a_dry_run_also_refuses_an_empty_human_pass(tmp_path):
    path = _labelled_sheet(tmp_path / "judge", ["true"] * 19 + [""])
    assert judge.main(["run", "--dry-run", "--dir", str(path.parent)]) == 1


# End to end on fake labels -------------------------------------------------------------------------------------


def test_dry_run_then_kappa_end_to_end(tmp_path, capsys):
    path = _labelled_sheet(tmp_path / "judge")
    before = path.read_bytes()
    assert judge.main(["run", "--dry-run", "--dir", str(path.parent)]) == 0
    printed = capsys.readouterr().out
    assert "True" not in printed and "False" not in printed and "pass" not in printed.lower()  # never a verdict
    config = json.loads((path.parent / "config.json").read_text(encoding="utf-8"))
    assert config["labels_sha256"] == judge.lf_sha256(path) and config["n_calls"] == 21
    assert config["complete"] is True and config["smoke"][0]["valid"] is True
    assert config["not_for_reporting_reasons"]

    assert judge.main(["kappa", "--dir", str(path.parent)]) == 0
    report = json.loads((path.parent / "kappa.json").read_text(encoding="utf-8"))
    assert path.read_bytes() == before  # the sheet is never written by run or kappa
    # the fake judge passes every answer; the fake labels are 13 true, 7 false
    assert report["raw_agreement"]["k"] == 13 and report["human_pass_rate"]["k"] == 13
    assert report["confusion_matrix"]["human_fail"] == {"judge_pass": 7, "judge_fail": 0, "judge_invalid": 0}
    assert report["cohen_kappa"] == 0.0
    assert len(report["disagreements"]) == 7
    summary = (path.parent / "summary.md").read_text(encoding="utf-8")
    assert summary.startswith("**NOT FOR REPORTING**") and "qwen" not in report["conditions"]
    assert judge.main(["run", "--dry-run", "--dir", str(path.parent)]) == 1  # outputs exist, no --resume


def test_kappa_refuses_labels_changed_after_the_run(tmp_path):
    path = _labelled_sheet(tmp_path / "judge")
    assert judge.main(["run", "--dry-run", "--dir", str(path.parent)]) == 0
    path.write_bytes(path.read_bytes().replace(b",true,", b",false,", 1))
    assert judge.main(["kappa", "--dir", str(path.parent)]) == 1


def _smoke_reply() -> str:
    criteria = judge.criteria_list(judge.SMOKE["must_include"], judge.SMOKE["must_not"])
    return reply([{**c, "met": False, "evidence": ""} for c in criteria])


def test_smoke_call_with_another_model_stops_the_run(tmp_path, monkeypatch, capsys):
    path = _labelled_sheet(tmp_path / "judge")
    monkeypatch.setattr(judge, "DryRunJudgeClient", lambda: ScriptedJudge([_smoke_reply()], returned="other/model"))
    assert judge.main(["run", "--dry-run", "--dir", str(path.parent)]) == 1
    assert "not switched" in capsys.readouterr().err
    assert not (path.parent / judge.OUTPUTS).exists()


def test_smoke_call_api_error_stops_the_run(tmp_path, monkeypatch, capsys):
    path = _labelled_sheet(tmp_path / "judge")
    failed = LLMResponse("", "fake-judge", 0, 0, 0.0, error="APIConnectionError()", model_requested="fake-judge")
    monkeypatch.setattr(judge, "DryRunJudgeClient", lambda: ScriptedJudge([failed]))
    assert judge.main(["run", "--dry-run", "--dir", str(path.parent)]) == 1
    assert "API error" in capsys.readouterr().err
    config = json.loads((path.parent / "config.json").read_text(encoding="utf-8"))
    assert config["complete"] is False and config["stopped"].startswith("smoke call")


def test_smoke_call_invalid_twice_stops_the_run(tmp_path, monkeypatch, capsys):
    path = _labelled_sheet(tmp_path / "judge")
    monkeypatch.setattr(judge, "DryRunJudgeClient", lambda: ScriptedJudge(["no", "still no"]))
    assert judge.main(["run", "--dry-run", "--dir", str(path.parent)]) == 1
    assert "invalid reply twice" in capsys.readouterr().err


class FailOnCall(judge.DryRunJudgeClient):
    """The offline judge, but call number `fail_at` returns an API error."""

    def __init__(self, fail_at: int):
        super().__init__()
        self.fail_at, self.n = fail_at, 0

    def chat(self, messages, temperature):
        self.n += 1
        if self.n == self.fail_at:
            return LLMResponse("", self.model, 0, 0, 0.0, error="RateLimitError()", model_requested=self.model)
        return super().chat(messages, temperature)


def test_an_api_error_stops_the_run_and_resume_finishes_it(tmp_path, monkeypatch):
    path = _labelled_sheet(tmp_path / "judge")
    folder = str(path.parent)
    monkeypatch.setattr(judge, "DryRunJudgeClient", lambda: FailOnCall(6))  # smoke + 4 rows, then an error
    assert judge.main(["run", "--dry-run", "--dir", folder]) == 1
    assert len(judge.load_jsonl(path.parent / judge.OUTPUTS)) == 4  # the failed row is not recorded
    assert judge.main(["kappa", "--dir", folder]) == 1  # outputs do not cover every row
    assert judge.main(["run", "--dry-run", "--dir", folder]) == 1  # needs --resume
    monkeypatch.setattr(judge, "DryRunJudgeClient", lambda: FailOnCall(0))
    assert judge.main(["run", "--dry-run", "--resume", "--dir", folder]) == 0
    records = judge.load_jsonl(path.parent / judge.OUTPUTS)
    assert len(records) == 20 and len({(r["id"], r["source_run"]) for r in records}) == 20
    config = json.loads((path.parent / "config.json").read_text(encoding="utf-8"))
    assert config["complete"] and config["call_errors"] == 1 and config["n_calls"] == 6 + 17
    assert len(config["sessions"]) == 2 and len(config["smoke"]) == 2
    assert judge.main(["kappa", "--dir", folder]) == 0


def test_kappa_is_not_for_reporting_when_another_model_answered():
    config = {
        "commit": "abc",
        "model": {"requested": "m", "returned": ["m", "other"]},
        "prompt_version": "judge_v1",
        "temperature": 0.0,
        "labels_sha256": "0" * 64,
        "labels_commit": "abc",
        "complete": True,
    }
    sheet = [{"id": "x0", "source_run": judge.V1_RUN, "human_pass": "true"}]
    records = [{"id": "x0", "source_run": judge.V1_RUN, "valid": True, "judge_pass": True, "items": [], "attempts": []}]
    report = judge.kappa_report(sheet, records, config)
    assert not report["for_reporting"] and "models returned" in report["not_for_reporting_reasons"][0]


def test_an_invalid_judge_row_counts_as_a_disagreement():
    sheet = [{"id": f"x{i}", "source_run": judge.V1_RUN, "human_pass": h} for i, h in enumerate(["true", "false"])]
    records = [
        {"id": "x0", "source_run": judge.V1_RUN, "valid": False, "judge_pass": None, "items": None, "attempts": []},
        {"id": "x1", "source_run": judge.V1_RUN, "valid": True, "judge_pass": False, "items": [], "attempts": []},
    ]
    config = {
        "commit": "abc",
        "model": {"requested": "m", "returned": ["m"]},
        "prompt_version": "judge_v1",
        "temperature": 0.0,
        "labels_sha256": "0" * 64,
        "labels_commit": "abc",
        "complete": True,
    }
    report = judge.kappa_report(sheet, records, config)
    assert report["for_reporting"]
    assert report["raw_agreement"]["k"] == 1 and report["invalid_judge_rows"] == 1
    assert report["confusion_matrix"]["human_pass"]["judge_invalid"] == 1
    assert [d["id"] for d in report["disagreements"]] == ["x0"]
    assert "counted as a disagreement" in report["disagreements"][0]["judge_reason"]
