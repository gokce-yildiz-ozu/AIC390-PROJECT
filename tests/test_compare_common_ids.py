"""compare.py --common-ids: a planned subset run against a full run (synthetic runs only)."""

import json

import pytest
from test_run_e2e import _write_run, compare, run_e2e


def mark_subset(folder, extra_reasons=()):
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    (folder / "config.json").write_text(json.dumps({**config, "subset": True}), encoding="utf-8")
    reasons = [compare.SUBSET_REASON, *extra_reasons]
    (folder / "summary.json").write_text(json.dumps({"not_for_reporting_reasons": reasons}), encoding="utf-8")


def runs(tmp_path):
    subset = _write_run(tmp_path / "a", "runA", [True, False, False])
    full = _write_run(tmp_path / "b", "ref", [True, True, False, False, False])
    return subset, full


def test_both_sides_are_cut_to_the_shared_cases(tmp_path):
    a, b = runs(tmp_path)
    result = compare.compare(compare.load_run(a), compare.load_run(b), common_ids=True)
    assert (result["n"], result["b"], result["c"]) == (3, 0, 1)
    assert result["A"]["accuracy"]["n"] == result["B"]["accuracy"]["n"] == 3
    assert (result["A"]["accuracy"]["k"], result["B"]["accuracy"]["k"]) == (1, 2)
    common = result["common_ids"]
    assert (common["n_common"], common["A_total"], common["B_total"]) == (3, 3, 5)
    assert common["left_out_of_A"] == [] and common["left_out_of_B"] == ["c03", "c04"]


def test_without_the_flag_different_ids_are_still_refused(tmp_path):
    a, b = runs(tmp_path)
    with pytest.raises(ValueError, match="case ids"):
        compare.compare(compare.load_run(a), compare.load_run(b))


def test_a_planned_subset_run_is_listed_but_does_not_block_reporting(tmp_path):
    a, b = runs(tmp_path)
    mark_subset(a)
    result = compare.compare(compare.load_run(a), compare.load_run(b), common_ids=True)
    assert result["for_reporting"] is True and result["common_ids"]["subset_runs"] == ["runA"]


def test_every_other_reason_still_blocks_reporting(tmp_path):
    a, b = runs(tmp_path)
    mark_subset(a, ["run did not finish"])
    result = compare.compare(compare.load_run(a), compare.load_run(b), common_ids=True)
    assert result["not_for_reporting_reasons"] == ["runA: run did not finish"]


def test_no_shared_cases_different_sets_and_repeat_are_refused(tmp_path):
    a, b = runs(tmp_path)
    first, second = compare.load_run(a), compare.load_run(b)
    with pytest.raises(ValueError, match="no case ids in common"):
        compare.compare({**first, "outputs": {}}, second, common_ids=True)
    other = _write_run(tmp_path / "c", "other", [True], sha="0" * 64)
    with pytest.raises(ValueError, match="cases_sha256"):
        compare.compare(first, compare.load_run(other), common_ids=True)
    with pytest.raises(ValueError, match="repeat"):
        compare.compare(first, second, repeat=True, common_ids=True)


def test_the_result_folder_says_common_ids(tmp_path, monkeypatch):
    out = tmp_path / "results"
    monkeypatch.setattr(compare, "RESULTS_DIR", out)
    monkeypatch.setattr(compare, "rel", str)
    a, b = runs(tmp_path)
    assert compare.main([str(a), str(b), "--common-ids"]) == 0
    (folder,) = out.iterdir()
    assert folder.name.endswith("_compare_runA_vs_ref_common-ids")


def test_the_subset_reason_is_the_text_the_harness_writes():
    config = {"dry_run": False, "frozen": True, "dirty": [], "subset": True}
    assert run_e2e.reporting_problems(config, True, []) == [compare.SUBSET_REASON]
