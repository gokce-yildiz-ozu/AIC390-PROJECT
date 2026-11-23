"""W2.5 paired comparison of two e2e runs (eval/run_e2e.py) on the same frozen cases: exact McNemar test.

    python eval/compare.py results/<run A> results/<run B>
    python eval/compare.py results/<run A> --repeat results/<run A, second run>   # run-to-run flips
    python eval/compare.py results/<run A> results/<run B> --common-ids           # a planned subset vs a full run

Both runs must have the same cases_sha256 and the same case ids. With --common-ids the ids may differ: both sides are
cut to the cases they share, and the output lists what was left out of each. b = cases only A got right,
c = cases only B got right; cases both got right or both got wrong do not enter the test. Writes
results/<date>_compare_<A label>_vs_<B label>/compare.json (or _repeat_ for --repeat).
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from aic390.stats import mcnemar_exact

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_e2e import CODE_FIELDS, RESULTS_DIR, grade, is_correct, proportion, rel  # noqa: E402

SCRIPT = "eval/compare.py"
MIN_DISCORDANT = 6  # with b + c < 6 even an all-one-way split gives p > 0.05
SUBSET_REASON = "subset of the test set (--ids / --limit)"  # written by run_e2e.reporting_problems
SAME_SYSTEM_KEYS = ("prompts", "temperature", "search", "table", "split_filter")


def load_run(folder: Path) -> dict:
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    outputs = {}
    for line in (folder / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            stored = record["correct"]
            record["correct"] = regraded(record)
            record["stored_correct"] = stored
            outputs[record["id"]] = record
    summary_path = folder / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    return {"folder": folder, "config": config, "outputs": outputs, "summary": summary}


def regraded(record: dict) -> bool:
    """Grade the stored output again with the current rules, so both runs of a pair share one grading rule."""
    if record.get("error") is not None or record.get("output") is None:
        return False
    return is_correct(grade(record["expected"], record["output"])[0])


def label(run: dict) -> str:
    return run["config"].get("label") or run["folder"].name


def pair_problems(a: dict, b: dict, same_system: bool = False) -> list[str]:
    problems = []
    if a["config"]["cases_sha256"] != b["config"]["cases_sha256"]:
        problems.append(f"different cases_sha256: {a['config']['cases_sha256']} vs {b['config']['cases_sha256']}")
    if set(a["outputs"]) != set(b["outputs"]):
        only_a = sorted(set(a["outputs"]) - set(b["outputs"]))
        only_b = sorted(set(b["outputs"]) - set(a["outputs"]))
        problems.append(f"different case ids: only in A {only_a}, only in B {only_b}")
    if same_system:
        if a["config"]["model"]["requested"] != b["config"]["model"]["requested"]:
            problems.append("different model")
        if a["config"].get("commit") != b["config"].get("commit"):
            problems.append("different commit")
        problems += [f"different {k}" for k in SAME_SYSTEM_KEYS if a["config"].get(k) != b["config"].get(k)]
    return problems


def cut_to_common(a: dict, b: dict) -> tuple[dict, dict, dict]:
    """Both runs on the ids they share, and a record of what each side had and lost."""
    ids = set(a["outputs"]) & set(b["outputs"])
    if not ids:
        raise ValueError("no case ids in common")

    def cut(run: dict) -> dict:
        return {**run, "outputs": {i: r for i, r in run["outputs"].items() if i in ids}}

    info = {
        "n_common": len(ids),
        "ids": sorted(ids),
        "A_total": len(a["outputs"]),
        "B_total": len(b["outputs"]),
        "left_out_of_A": sorted(set(a["outputs"]) - ids),
        "left_out_of_B": sorted(set(b["outputs"]) - ids),
        "subset_runs": [label(r) for r in (a, b) if r["config"].get("subset")],
    }
    return cut(a), cut(b), info


def not_for_reporting(run: dict, allow_subset: bool = False) -> list[str]:
    """allow_subset: a comparison on common ids may use a run made with --ids. It is listed in
    common_ids.subset_runs; every other reason (dirty tree, unfinished run, ...) still blocks."""
    name = label(run)
    reasons = [] if run["summary"] is not None else ["no summary.json"]
    if run["summary"] is not None:
        reasons += run["summary"].get("not_for_reporting_reasons", [])
    if allow_subset:
        reasons = [r for r in reasons if r != SUBSET_REASON]
    changed = sorted(i for i, r in run["outputs"].items() if r["correct"] != r["stored_correct"])
    if changed:
        reasons.append(f"grading changed since the run (regraded: {', '.join(changed)})")
    return [f"{name}: {reason}" for reason in reasons]


def _side(run: dict) -> dict:
    outputs = run["outputs"].values()
    return {
        "folder": rel(run["folder"]),
        "label": label(run),
        "commit": run["config"].get("commit"),
        "prompts": run["config"].get("prompts"),
        "accuracy": proportion(sum(r["correct"] for r in outputs), len(outputs)),
    }


def mcnemar(a: dict, b: dict) -> dict:
    ids = sorted(a["outputs"])
    only_a = [i for i in ids if a["outputs"][i]["correct"] and not b["outputs"][i]["correct"]]
    only_b = [i for i in ids if b["outputs"][i]["correct"] and not a["outputs"][i]["correct"]]
    result = {
        "n": len(ids),
        "b": len(only_a),
        "c": len(only_b),
        "b_ids": only_a,
        "c_ids": only_b,
        "p_value": mcnemar_exact(len(only_a), len(only_b)),
        "test": "exact McNemar, two-sided (aic390.stats.mcnemar_exact), on outputs regraded by eval/run_e2e.py",
        "note": None,
    }
    if len(only_a) + len(only_b) < MIN_DISCORDANT:
        result["note"] = "too few discordant pairs to detect a difference"
    return result


def _graded_output(record: dict) -> dict | None:
    output = record["output"]
    return None if output is None else {f: output.get(f) for f in CODE_FIELDS}


def repeat_changes(a: dict, b: dict) -> dict:
    ids = sorted(a["outputs"])
    flips = [i for i in ids if a["outputs"][i]["correct"] != b["outputs"][i]["correct"]]
    graded = [i for i in ids if _graded_output(a["outputs"][i]) != _graded_output(b["outputs"][i])]
    text = [
        i
        for i in ids
        if (a["outputs"][i]["output"] or {}).get("answer_text") != (b["outputs"][i]["output"] or {}).get("answer_text")
    ]
    return {
        "correct_flips": len(flips),
        "correct_flip_ids": flips,
        "graded_output_changed": len(graded),
        "graded_output_changed_ids": graded,
        "answer_text_changed": len(text),
        "answer_text_changed_ids": text,
    }


def compare(a: dict, b: dict, repeat: bool = False, common_ids: bool = False) -> dict:
    if repeat and common_ids:
        raise ValueError("--common-ids does not apply to --repeat: a repeat run has the same cases")
    common = None
    if common_ids:
        a, b, common = cut_to_common(a, b)
    problems = pair_problems(a, b, same_system=repeat)
    if problems:
        raise ValueError("; ".join(problems))
    reasons = not_for_reporting(a, common_ids) + not_for_reporting(b, common_ids)
    result = {
        "mode": "repeat" if repeat else "compare",
        "for_reporting": not reasons,
        "not_for_reporting_reasons": reasons,
        "cases_sha256": a["config"]["cases_sha256"],
        "common_ids": common,
        "A": _side(a),
        "B": _side(b),
        **mcnemar(a, b),
        "script": SCRIPT,
    }
    if repeat:
        result.update(repeat_changes(a, b))
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("A", type=Path, help="results folder of run A")
    ap.add_argument("B", type=Path, nargs="?", default=None, help="results folder of run B")
    ap.add_argument("--repeat", type=Path, default=None, help="a second run of the same system as A: count flips")
    ap.add_argument("--common-ids", action="store_true", help="compare on the cases both runs have")
    args = ap.parse_args(argv)
    if (args.B is None) == (args.repeat is None):
        print("error: give either B or --repeat A2", file=sys.stderr)
        return 1
    try:
        a = load_run(args.A)
        b = load_run(args.B or args.repeat)
        result = compare(a, b, repeat=args.repeat is not None, common_ids=args.common_ids)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    name = f"{date.today().isoformat()}_{result['mode']}_{result['A']['label']}_vs_{result['B']['label']}"
    name += "_common-ids" if args.common_ids else ""
    out = RESULTS_DIR / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "compare.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"wrote {rel(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
