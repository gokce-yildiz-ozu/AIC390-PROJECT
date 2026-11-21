"""Offline tests for the W2.4 harness and the W2.5 comparison: hand-written outputs and the fake model only."""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import compare  # noqa: E402
import run_e2e  # noqa: E402

CASES = ROOT / "eval" / "testsets" / "week2_cases.jsonl"
README_HASH = "787059b6aa2be9411a6dc135480f948453f008bc1ab6b92d3f3b63542b75f8b4"

CONFIG_KEYS = {
    "commit",
    "dirty",
    "model",
    "temperature",
    "prompts",
    "cases_path",
    "cases_sha256",
    "frozen",
    "split_filter",
    "ids",
    "n",
    "search",
    "table",
    "judge_fields",
    "started_at",
    "finished_at",
    "n_calls",
    "sleep_s",
    "argv",
}

HW2 = {
    "course": "CS-301",
    "item": "Homework 2",
    "item_key": "hw2",
    "due_date": "2026-11-20",
    "due_time": "23:59",
    "due_candidates": [],
    "status": "new",
    "supersedes": None,
}
LAB3 = {
    "course": "CS-301",
    "item": "Lab Report 3",
    "item_key": "labreport3",
    "due_date": None,
    "due_time": None,
    "due_candidates": [{"date": "2026-11-13", "time": "23:59"}, {"date": "2026-11-20", "time": "23:59"}],
    "status": "new",
    "supersedes": None,
}
REMINDER = {"type": "create_reminder", "remind_at": "2026-11-22T23:59:00+03:00", "requires_confirmation": True}


def expected(**fields) -> dict:
    base = {
        "intent": "deadline_message",
        "deadlines": [],
        "ask_user": False,
        "abstain": False,
        "sources": [],
        "must_include": [],
        "must_not": [],
        "answer_language": None,
        "action": None,
        "count": None,
        "untrusted_flag": False,
    }
    return {**base, **copy.deepcopy(fields)}


def output_for(exp: dict, **fields) -> dict:
    out = {k: copy.deepcopy(v) for k, v in exp.items() if k not in run_e2e.JUDGE_FIELDS}
    return {**out, "answer_text": "", **copy.deepcopy(fields)}


def graded(exp: dict, out: dict) -> tuple[dict, int, bool]:
    fields, extra = run_e2e.grade(exp, out)
    return fields, extra, run_e2e.is_correct(fields)


# Grading ------------------------------------------------------------------------------------------------------


def test_identical_output_is_correct():
    exp = expected(deadlines=[HW2, LAB3], ask_user=True)
    _, _, correct = graded(exp, output_for(exp))
    assert correct


def test_deadline_set_with_a_missing_row_fails():
    exp = expected(deadlines=[HW2, LAB3])
    fields, _, correct = graded(exp, output_for(exp, deadlines=[HW2]))
    assert fields["deadlines"] is False and not correct


def test_deadline_set_with_an_extra_row_fails():
    exp = expected(deadlines=[HW2])
    fields, _, correct = graded(exp, output_for(exp, deadlines=[HW2, LAB3]))
    assert fields["deadlines"] is False and not correct


def test_duplicate_output_row_fails():
    exp = expected(deadlines=[HW2])
    fields, _, _ = graded(exp, output_for(exp, deadlines=[HW2, HW2]))
    assert fields["deadlines"] is False


def test_item_differing_alone_passes():
    exp = expected(deadlines=[HW2])
    fields, _, correct = graded(exp, output_for(exp, deadlines=[{**HW2, "item": "HW 2"}]))
    assert fields["deadlines"] is True and correct


def test_due_candidates_in_another_order_pass():
    exp = expected(deadlines=[LAB3])
    reordered = {**LAB3, "due_candidates": list(reversed(LAB3["due_candidates"]))}
    fields, _, correct = graded(exp, output_for(exp, deadlines=[reordered]))
    assert fields["deadlines"] is True and correct


@pytest.mark.parametrize(
    "change",
    [
        {"due_date": "2026-11-21"},
        {"due_time": None},
        {"status": "updated"},
        {"supersedes": {"date": "2026-11-13", "time": "23:59"}},
        {"item_key": "hw02"},
    ],
)
def test_a_wrong_row_field_fails(change):
    exp = expected(deadlines=[HW2])
    fields, _, _ = graded(exp, output_for(exp, deadlines=[{**HW2, **change}]))
    assert fields["deadlines"] is False


def test_extra_sources_pass_and_are_counted():
    exp = expected(intent="rule_question", sources=[{"doc_id": "cs301-syllabus", "section": "Late policy"}])
    cited = exp["sources"] + [
        {"doc_id": "regulation-article-14", "section": "Article 14"},
        {"doc_id": "cs310-syllabus-v2", "section": "Late policy"},
    ]
    fields, extra, correct = graded(exp, output_for(exp, sources=cited))
    assert fields["sources"] is True and extra == 2 and correct


def test_a_missing_expected_source_fails():
    exp = expected(sources=[{"doc_id": "cs301-syllabus", "section": "Late policy"}])
    fields, _, _ = graded(exp, output_for(exp, sources=[{"doc_id": "cs301-syllabus", "section": "Schedule"}]))
    assert fields["sources"] is False


def test_answer_language_null_is_skipped():
    exp = expected(answer_language=None)
    fields, _, correct = graded(exp, output_for(exp, answer_language="tr"))
    assert fields["answer_language"] is None and correct
    exp = expected(answer_language="en")
    fields, _, correct = graded(exp, output_for(exp, answer_language="tr"))
    assert fields["answer_language"] is False and not correct


def test_judge_fields_never_affect_correct():
    exp = expected(intent="rule_question", must_include=["10%"], must_not=["5%"])
    fields, _, correct = graded(exp, output_for(exp, answer_text="Late work loses 5% per day."))
    assert fields["must_include"] is None and fields["must_not"] is None and correct


def test_action_null_vs_null_passes_and_fields_are_exact():
    exp = expected(intent="reminder")
    assert graded(exp, output_for(exp))[0]["action"] is True
    assert graded(exp, output_for(exp, action=REMINDER))[0]["action"] is False
    exp = expected(intent="reminder", action=REMINDER)
    assert graded(exp, output_for(exp, action=None))[0]["action"] is False
    late = {**REMINDER, "remind_at": "2026-11-23T09:00:00+03:00"}
    assert graded(exp, output_for(exp, action=late))[0]["action"] is False
    assert graded(exp, output_for(exp, action={**REMINDER, "requires_confirmation": False}))[0]["action"] is False


@pytest.mark.parametrize("field,value", [("intent", "lookup"), ("ask_user", True), ("count", 3), ("abstain", True)])
def test_exact_fields(field, value):
    exp = expected()
    fields, _, correct = graded(exp, output_for(exp, **{field: value}))
    assert fields[field] is False and not correct


# Frozen-set check ---------------------------------------------------------------------------------------------


def test_readme_hash_is_found_for_the_week2_set():
    assert run_e2e.recorded_sha256(CASES) == README_HASH


def test_a_cases_file_with_crlf_endings_gives_the_readme_hash(tmp_path):
    lf = CASES.read_bytes().replace(b"\r\n", b"\n")
    crlf = tmp_path / "week2_cases.jsonl"
    crlf.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert b"\r\n" in crlf.read_bytes()
    assert run_e2e.lf_sha256(crlf) == README_HASH


@pytest.fixture
def results_dir(tmp_path, monkeypatch):
    out = tmp_path / "results"
    monkeypatch.setattr(run_e2e, "RESULTS_DIR", out)
    monkeypatch.setattr(compare, "RESULTS_DIR", out)
    return out


def _modified_copy(tmp_path: Path) -> Path:
    lines = CASES.read_text(encoding="utf-8").splitlines()
    path = tmp_path / "week2_cases.jsonl"
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")  # one case fewer, still valid JSONL
    return path


def test_a_modified_cases_file_is_refused_without_unfrozen(tmp_path, results_dir):
    modified = _modified_copy(tmp_path)
    assert run_e2e.main(["--dry-run", "--cases", str(modified), "--limit", "1", "--label", "t"]) == 1
    assert not results_dir.exists()


def test_unfrozen_run_is_recorded_and_marked_not_for_reporting(tmp_path, results_dir):
    modified = _modified_copy(tmp_path)
    assert run_e2e.main(["--dry-run", "--cases", str(modified), "--limit", "1", "--label", "t", "--unfrozen"]) == 0
    (folder,) = results_dir.iterdir()
    assert json.loads((folder / "config.json").read_text(encoding="utf-8"))["frozen"] is False
    assert (folder / "summary.md").read_text(encoding="utf-8").startswith("**NOT FOR REPORTING**")


def test_held_out_set_uses_its_sibling_sha256(tmp_path, results_dir):
    held = tmp_path / "heldout_v1.jsonl"
    held.write_bytes(CASES.read_bytes())
    args = ["--dry-run", "--cases", str(held), "--limit", "1", "--label", "h"]
    assert run_e2e.main(args) == 1  # no .sha256 yet
    run_e2e.sha256_file(held).write_text("0" * 64 + "\n", encoding="utf-8")
    assert run_e2e.main(args) == 1  # wrong hash
    run_e2e.sha256_file(held).write_text(run_e2e.lf_sha256(held) + "\n", encoding="utf-8")
    assert run_e2e.main(args) == 0
    (folder,) = results_dir.iterdir()
    assert json.loads((folder / "config.json").read_text(encoding="utf-8"))["frozen"] is True


# Dry run ------------------------------------------------------------------------------------------------------


def test_dry_run_writes_four_files_and_every_config_key(results_dir):
    assert run_e2e.main(["--dry-run", "--limit", "3", "--label", "dryrun"]) == 0
    (folder,) = results_dir.iterdir()
    assert folder.name.endswith("_e2e_dryrun_fake-model")
    assert {p.name for p in folder.iterdir()} == {"config.json", "outputs.jsonl", "summary.json", "summary.md"}
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    assert CONFIG_KEYS <= set(config)
    assert config["model"] == {"requested": "fake-model", "returned": ["fake-model"]}
    assert config["cases_sha256"] == README_HASH and config["frozen"] is True
    assert config["judge_fields"] == "not graded" and config["search"]["backend"] == "stub"
    assert config["table"]["source"] == "seed" and config["table"]["rows_from_cases"] > 0
    assert set(config["prompts"]) == {"classifier", "extract", "answer", "lookup"}
    assert config["n"] == 3 and len(config["ids"]) == 3 and config["finished_at"]
    records = [json.loads(line) for line in (folder / "outputs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in records] == config["ids"]
    assert all("trace" in r["output"] and "expected" in r for r in records)
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["n_calls"] == config["n_calls"] == sum(len(r["calls"]) for r in records) > 0
    assert summary["for_reporting"] is False


def test_docs_only_table_drops_rows_created_from_cases():
    table, info = run_e2e.load_table("docs-only")
    assert info["rows_from_cases"] == 0 and info["rows"] == len(table.rows) > 0
    assert all(not r["origin"].startswith("w") for r in table.rows)
    _, seed = run_e2e.load_table("seed")
    assert seed["rows"] > info["rows"] and seed["sha256"] == info["sha256"]


def test_a_raising_run_case_counts_as_incorrect_and_the_run_continues(results_dir, monkeypatch):
    def broken(case, client, search=None, table=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(run_e2e, "run_case", broken)
    assert run_e2e.main(["--dry-run", "--limit", "2", "--label", "err"]) == 2
    (folder,) = results_dir.iterdir()
    records = [json.loads(line) for line in (folder / "outputs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2 and all(r["error"] and r["correct"] is False for r in records)
    assert all(v is None for r in records for v in r["fields"].values())  # no field is blamed for a crash


def test_prompts_option_needs_the_run_case_parameter(results_dir, monkeypatch):
    def without_prompts(case, client, search=None, table=None):
        return {}

    monkeypatch.setattr(run_e2e, "run_case", without_prompts)
    assert run_e2e.main(["--dry-run", "--limit", "1", "--prompts", "extract=extract_v1"]) == 1
    assert not results_dir.exists()


def test_sleep_happens_between_calls_only():
    slept = []
    client = run_e2e.CountingClient(run_e2e.FakeClient(), sleep_s=13, sleep=slept.append)
    for _ in range(3):
        client.chat([{"role": "user", "content": "x"}], temperature=0)
    assert slept == [13, 13] and len(client.calls) == 3
    assert client.slept_s < 1  # the measured pause, not the nominal 13 s: the fake sleep returns at once


def test_latency_excludes_the_harness_sleep(monkeypatch):
    def two_calls(case, client, search=None, table=None):
        for _ in range(2):
            client.chat([{"role": "user", "content": "x"}], temperature=0)
        return {}

    monkeypatch.setattr(run_e2e, "run_case", two_calls)
    client = run_e2e.CountingClient(run_e2e.FakeClient(), sleep_s=0.3)
    case = {"id": "x1", "expected": expected()}
    (record,) = run_e2e.run_cases([case], client, search=None, table=None)
    assert client.slept_s >= 0.3 and record["latency_s"] < 0.2 and len(record["calls"]) == 2


def test_split_filter_and_scoreboard_refusal(results_dir):
    assert run_e2e.main(["--dry-run", "--split", "new", "--limit", "2", "--label", "s"]) == 0
    (folder,) = results_dir.iterdir()
    records = [json.loads(line) for line in (folder / "outputs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["split"] for r in records] == ["new", "new"]
    assert run_e2e.main(["--dry-run", "--label", "sb", "--write-scoreboard"]) == 1


def test_files_outside_the_commit_are_reported(tmp_path):
    loose = tmp_path / "loose.md"
    loose.write_text("x", encoding="utf-8")
    untracked = run_e2e.git_untracked([run_e2e.SEED, loose])
    assert untracked is not None and loose.as_posix() in untracked
    assert "data/db/deadlines_seed.jsonl" not in untracked
    config = _config(untracked=[loose.as_posix()])
    assert any("not in the commit" in p for p in run_e2e.reporting_problems(config, True, []))


# Summary ------------------------------------------------------------------------------------------------------


def _record(case_id, case_type, exp_abstain, out_abstain, correct, split="new"):
    fields = {f: correct for f in run_e2e.CODE_FIELDS} | {f: None for f in run_e2e.JUDGE_FIELDS}
    return {
        "id": case_id,
        "split": split,
        "type": case_type,
        "correct": correct,
        "fields": fields,
        "extra_sources": 0,
        "error": None,
        "latency_s": 1.0,
        "calls": [],
        "output": {"abstain": out_abstain, "trace": []},
        "expected": {"abstain": exp_abstain},
    }


def _config(**over):
    config = {
        "model": {"requested": "fake-model", "returned": []},
        "temperature": 0.0,
        "prompts": run_e2e.default_prompts(),
        "search": {"backend": "stub"},
        "table": {"rows_from_cases": 17},
        "dry_run": False,
        "frozen": True,
        "dirty": [],
        "subset": False,
        "wall_time_s": 1.0,
    }
    return {**config, **over}


def test_refusal_metrics_use_their_own_denominators():
    records = [
        _record("u1", "unanswerable", True, True, True),
        _record("u2", "unanswerable", True, False, False),
        _record("a1", "adversarial", True, True, True),
        _record("a2", "adversarial", False, True, False),  # adversarial, but should be answered
        _record("n1", "normal", False, True, False),
        _record("n2", "normal", False, False, True, split="seen"),
    ]
    summary = run_e2e.summarize(records, _config(), prices=None)
    assert (summary["abstention_correct"]["k"], summary["abstention_correct"]["n"]) == (1, 2)
    assert (summary["adversarial_refusal"]["k"], summary["adversarial_refusal"]["n"]) == (1, 1)
    assert (summary["false_abstentions"]["k"], summary["false_abstentions"]["n"]) == (2, 3)
    assert summary["accuracy"]["k"] == 3 and summary["by_split"]["seen"]["n"] == 1
    assert summary["accuracy"]["ci95_wilson"] != summary["accuracy"]["ci95_normal"]
    assert summary["for_reporting"] is True and set(summary["definitions"]) == set(run_e2e.DEFINITIONS)


def test_scoreboard_only_from_a_reportable_run():
    records = [_record("u1", "unanswerable", True, True, True), _record("n1", "normal", False, False, False)]
    board = run_e2e.scoreboard_from(run_e2e.summarize(records, _config(), prices=None), _config())
    assert board["week"] == 2 and board["test_set_size"] == 2
    assert board["e2e_accuracy"]["n"] == 2 and board["e2e_accuracy"]["script"] == "eval/run_e2e.py"
    assert board["hit_at_5"] is None and board["injection_success"] is None
    dirty = run_e2e.summarize(records, _config(dirty=["src/x.py"]), prices=None)
    with pytest.raises(ValueError):
        run_e2e.scoreboard_from(dirty, _config(dirty=["src/x.py"]))


# compare.py ---------------------------------------------------------------------------------------------------


def _graded_record(case_id: str, ok: bool, stored: bool | None = None) -> dict:
    """A record whose output really grades as ok; `stored` fakes a correct flag written by older grading."""
    exp = expected()
    out = output_for(exp) if ok else output_for(exp, intent="lookup")
    fields, extra = run_e2e.grade(exp, out)
    record = _record(case_id, "normal", False, False, ok if stored is None else stored)
    return {**record, "fields": fields, "extra_sources": extra, "output": {**out, "trace": []}, "expected": exp}


def _write_run(
    folder: Path, label: str, correct: list[bool], sha: str = README_HASH, stored: dict | None = None
) -> Path:
    folder.mkdir(parents=True)
    config = {**_config(), "label": label, "cases_sha256": sha, "split_filter": "all", "commit": "abc1234"}
    (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
    stored = stored or {}
    records = [_graded_record(f"c{i:02d}", ok, stored.get(i)) for i, ok in enumerate(correct)]
    (folder / "outputs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    summary = {"not_for_reporting_reasons": []}
    (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return folder


def test_compare_computes_b_c_and_the_exact_p_value(tmp_path, results_dir):
    a = _write_run(tmp_path / "a", "v1", [True, True, True, False, True, False])
    b = _write_run(tmp_path / "b", "v2", [False, False, True, True, False, False])
    result = compare.compare(compare.load_run(a), compare.load_run(b))
    assert (result["n"], result["b"], result["c"]) == (6, 3, 1)
    assert result["b_ids"] == ["c00", "c01", "c04"] and result["c_ids"] == ["c03"]
    assert result["p_value"] == pytest.approx(0.625)  # 2 * (C(4,0) + C(4,1)) / 2**4
    assert result["note"] == "too few discordant pairs to detect a difference"
    assert compare.main([str(a), str(b)]) == 0
    (folder,) = results_dir.iterdir()
    assert folder.name.endswith("_compare_v1_vs_v2")
    assert json.loads((folder / "compare.json").read_text(encoding="utf-8"))["b"] == 3


def test_compare_refuses_different_cases_sha256(tmp_path, results_dir):
    a = _write_run(tmp_path / "a", "v1", [True, False])
    b = _write_run(tmp_path / "b", "v2", [True, True], sha="0" * 64)
    with pytest.raises(ValueError, match="cases_sha256"):
        compare.compare(compare.load_run(a), compare.load_run(b))
    assert compare.main([str(a), str(b)]) == 1
    assert not results_dir.exists()


def test_compare_refuses_different_ids(tmp_path):
    a = _write_run(tmp_path / "a", "v1", [True, False, True])
    b = _write_run(tmp_path / "b", "v2", [True, False])
    with pytest.raises(ValueError, match="case ids"):
        compare.compare(compare.load_run(a), compare.load_run(b))


def test_repeat_counts_run_to_run_flips(tmp_path, results_dir):
    a = _write_run(tmp_path / "a", "v1", [True, True, False, False])
    a2 = _write_run(tmp_path / "a2", "v1-r2", [True, False, True, False])
    assert compare.main([str(a), "--repeat", str(a2)]) == 0
    (folder,) = results_dir.iterdir()
    result = json.loads((folder / "compare.json").read_text(encoding="utf-8"))
    assert result["mode"] == "repeat" and result["correct_flips"] == 2
    assert result["correct_flip_ids"] == ["c01", "c02"]


def test_compare_regrades_and_flags_a_changed_grading(tmp_path):
    a = _write_run(tmp_path / "a", "v1", [True, False], stored={1: True})  # stored flag from older grading
    b = _write_run(tmp_path / "b", "v2", [True, False])
    result = compare.compare(compare.load_run(a), compare.load_run(b))
    assert result["A"]["accuracy"]["k"] == 1 and result["b"] == 0
    assert result["for_reporting"] is False
    assert any("grading changed" in r for r in result["not_for_reporting_reasons"])
