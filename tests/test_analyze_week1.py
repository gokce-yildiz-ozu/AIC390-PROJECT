import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_week1 as aw  # noqa: E402


def row(i, t, label="correct", fabricated="n", output="text", ingredients="extraction"):
    return {
        "id": i,
        "temperature": str(t),
        "ingredients": ingredients,
        "expected": "",
        "output": output,
        "label": label,
        "fabricated": fabricated,
        "note": "",
    }


def record(i, t, text="text"):
    return {"id": i, "temperature": t, "text": text}


def test_validation_accepts_a_clean_table():
    rows = [row("w1-01", 0.0), row("w1-01", 0.7, "wrong", "y")]
    outputs = [record("w1-01", 0.0), record("w1-01", 0.7)]
    assert aw.validate_grading(rows, outputs, expected_rows=2) == []


def test_validation_ignores_only_crlf_vs_lf():
    outputs = [record("w1-01", 0.0, text="line 1\nline 2")]
    assert aw.validate_grading([row("w1-01", 0.0, output="line 1\r\nline 2")], outputs, expected_rows=1) == []
    problems = aw.validate_grading([row("w1-01", 0.0, output="line 1\r\nline 2 ")], outputs, expected_rows=1)
    assert len(problems) == 1 and "output differs" in problems[0]


def test_validation_rejects_fabricated_with_partial():
    rows = [row("w1-01", 0.0, label="partial", fabricated="y")]
    problems = aw.validate_grading(rows, [record("w1-01", 0.0)], expected_rows=1)
    assert len(problems) == 1 and "requires label 'wrong'" in problems[0]


def test_validation_rejects_bad_values_duplicates_count_and_changed_output():
    rows = [
        row("w1-01", 0.0, label="ok"),
        row("w1-01", 0.0, fabricated="maybe"),
        row("w1-02", 0.0, output="edited by hand"),
    ]
    outputs = [record("w1-01", 0.0), record("w1-02", 0.0)]
    problems = "\n".join(aw.validate_grading(rows, outputs, expected_rows=4))
    for needle in ("expected 4 rows", "label 'ok'", "duplicate", "fabricated 'maybe'", "output differs"):
        assert needle in problems


def test_validate_repeat_checks_ids_and_first_run_labels():
    grades = {("w1-01", 0.0): row("w1-01", 0.0), ("w1-02", 0.0): row("w1-02", 0.0, "wrong", "y")}
    good = [
        {"id": "w1-01", "run1_label": "correct", "run1_fabricated": "n", "identical_text": "y",
         "same_answer": "y", "repeat_label": "correct"},
        {"id": "w1-02", "run1_label": "wrong", "run1_fabricated": "y", "identical_text": "n",
         "same_answer": "n", "repeat_label": "partial"},
    ]  # fmt: skip
    assert aw.validate_repeat(good, grades, expected_rows=2) == []
    bad = [dict(good[0], run1_label="partial")]
    problems = "\n".join(aw.validate_repeat(bad, grades, expected_rows=2))
    assert "expected 2 rows" in problems
    assert "missing ['w1-02']" in problems
    assert "do not match grading.csv" in problems


def grades_for(labels: dict[str, str]) -> dict:
    return {(i, 0.0): row(i, 0.0, label=label) for i, label in labels.items()}


def test_p4_needs_two_of_five_wrong_at_t0():
    inputs = aw.P_INPUTS["P4"]
    one_wrong = grades_for({i: ("wrong" if n == 0 else "partial") for n, i in enumerate(inputs)})
    two_wrong = grades_for({i: ("wrong" if n < 2 else "correct") for n, i in enumerate(inputs)})
    assert aw.rule_p4(one_wrong)["verdict"] == "false"
    result = aw.rule_p4(two_wrong)
    assert result["verdict"] == "true"
    assert result["counts"] == {"wrong_t0": 2, "n": 5}


def test_p6_is_not_decided_between_the_bounds():
    inputs = [f"w1-{n:02d}" for n in range(1, 6)]
    grades = {}
    for n, i in enumerate(inputs):
        grades[(i, 0.0)] = row(i, 0.0, output="a")
        grades[(i, 0.7)] = row(i, 0.7)
        # Three outputs change at T=1.2, but only one of them changes label.
        grades[(i, 1.2)] = row(i, 1.2, label="wrong" if n == 0 else "correct", output="b" if n < 3 else "a")
    result = aw.rule_p6(grades)
    assert result["counts"]["b_lower_bound_label_differs"] == 1
    assert result["counts"]["b_upper_bound_text_differs"] == 3
    assert result["verdict"] == "not decided"


def test_proportion_reports_both_intervals():
    p = aw.proportion(0, 3)
    assert p["value"] == 0 and p["ci95_normal"] == [0.0, 0.0]
    assert p["ci95_wilson"][1] > 0
