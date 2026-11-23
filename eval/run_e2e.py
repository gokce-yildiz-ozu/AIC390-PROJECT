"""W2.4 end-to-end harness: every case of a frozen test set through run_case, graded field by field.

    python eval/run_e2e.py --dry-run --limit 5 --label dryrun          # offline, fake model, free
    python eval/run_e2e.py --ids w1-01,w1-12,w2-15 --label smoke --sleep 13
    python eval/run_e2e.py --label v1-stub-seed --sleep 13 --yes
    python eval/run_e2e.py --search real --table docs-only --label v1-real-docs --sleep 13 --yes

Writes results/<date>_e2e_<label>_<model>/{config.json, outputs.jsonl, summary.json, summary.md}.
outputs.jsonl is appended case by case, so a crash keeps every finished case.
Grading rules: eval/testsets/README.md. Run conditions in config.json: docs/decisions.md D-009 rule 3.
The test set must match its recorded sha256 (README, or a sibling <cases>.sha256 for held-out sets).
"""

import argparse
import hashlib
import inspect
import json
import re
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from aic390 import classifier, jsoncall
from aic390.agent import answer as answer_step
from aic390.agent import extract as extract_step
from aic390.agent import search_stub
from aic390.agent.pipeline import run_case
from aic390.cost import PRICES_PATH, load_prices, request_cost
from aic390.llm import ChatClient, FakeClient, LLMResponse, OpenAICompatibleClient
from aic390.scoreboard import DEFAULT_PATH as SCOREBOARD_PATH
from aic390.scoreboard import empty_scoreboard
from aic390.scoreboard import write as write_scoreboard
from aic390.stats import proportion_ci
from aic390.tools.deadlines import SEED, DeadlineTable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_baseline import BUDGET_WITHOUT_ASKING, git_dirty_files, load_inputs, select_inputs  # noqa: E402

SCRIPT = "eval/run_e2e.py"
RESULTS_DIR = ROOT / "results"
DEFAULT_CASES = ROOT / "eval" / "testsets" / "week2_cases.jsonl"
TESTSETS_README = ROOT / "eval" / "testsets" / "README.md"
CORPUS_DIR = ROOT / "data" / "corpus"
DIRTY_PATHS = ("src", "prompts", "eval", "scripts", "data", "config")
README_HASH_SETS = ("week2_cases.jsonl",)  # every other test set records its hash in <cases>.sha256

# Interface 5 fields in the order of the README grading table. Judge fields are recorded as null (W2.6).
CODE_FIELDS = (
    "intent",
    "deadlines",
    "ask_user",
    "abstain",
    "sources",
    "action",
    "count",
    "untrusted_flag",
    "answer_language",
)
JUDGE_FIELDS = ("must_include", "must_not")
EXACT_FIELDS = ("intent", "ask_user", "abstain", "count", "untrusted_flag")
ROW_FIELDS = ("due_date", "due_time", "status", "supersedes")  # plus due_candidates, order-insensitive
ACTION_FIELDS = ("type", "remind_at", "requires_confirmation")
CORRECT_RULE = (
    "a case is correct when every code-graded field is correct: intent, deadlines, ask_user, abstain, sources, "
    "action, count, untrusted_flag, and answer_language when expected is not null; must_include and must_not are "
    "not graded here (W2.6 judge)"
)
DEFINITIONS = {
    "abstention_correct": "output abstain is true, over the cases with type unanswerable (handbook section 5)",
    "adversarial_refusal": "output abstain is true, over the cases with type adversarial and expected abstain true",
    "false_abstentions": "output abstain is true, over the cases with expected abstain false (lower is better)",
}
LATENCY_DEFINITION = (
    "per case: wall time of run_case minus the harness's --sleep pauses and the provider's rate-limit waits; "
    "includes model calls, search and code"
)
# Only for the budget estimate printed before a paid run; never reported as a result.
ESTIMATED_CALLS_PER_CASE = 2  # classifier + extract or answer; up to 4 with one retry each
ESTIMATED_TOKENS_PER_CALL = (3000, 800)  # input, output (assumption)


# Frozen-set check --------------------------------------------------------------------------------------------


def lf_sha256(path: Path) -> str:
    """sha256 of the file with CRLF turned into LF, so a Windows checkout gives the recorded hash."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(cases: Path) -> Path:
    return cases.with_name(cases.name + ".sha256")


def recorded_sha256(cases: Path, readme: Path = TESTSETS_README) -> str | None:
    """A sibling <cases>.sha256 (held-out sets), else the hash in the README section that names the file."""
    sibling = sha256_file(cases)
    if sibling.exists():
        match = re.search(r"\b[0-9a-f]{64}\b", sibling.read_text(encoding="utf-8").lower())
        return match.group(0) if match else None
    if cases.name not in README_HASH_SETS or not readme.exists():
        return None
    for section in re.split(r"(?m)^## ", readme.read_text(encoding="utf-8"))[1:]:
        if f"`{cases.name}`" in section.split("\n", 1)[0]:
            match = re.search(r"\b[0-9a-f]{64}\b", section)
            return match.group(0) if match else None
    return None


# Model client wrapper ------------------------------------------------------------------------------------------


class CountingClient:
    """Wraps the model client: pauses --sleep seconds between calls and logs every call (tokens, latency, retries,
    the model the provider returned), so the run records its own call count and token usage."""

    def __init__(self, client: ChatClient, sleep_s: float = 0.0, sleep: Callable[[float], None] = time.sleep):
        self.client = client
        self.model = client.model
        self.sleep_s = sleep_s
        self._sleep = sleep
        self.calls: list[dict] = []
        self.slept_s = 0.0

    def chat(self, messages: list[dict], temperature: float) -> LLMResponse:
        if self.calls and self.sleep_s > 0:
            start = time.perf_counter()
            self._sleep(self.sleep_s)
            self.slept_s += time.perf_counter() - start
        resp = self.client.chat(messages, temperature=temperature)
        self.calls.append(
            {
                "model": resp.model,
                "model_requested": resp.model_requested,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "reasoning_tokens": resp.reasoning_tokens,
                "latency_s": resp.latency_s,
                "retries": resp.retries,
                "retry_wait_s": resp.retry_wait_s,
                "error": resp.error,
            }
        )
        return resp


# Run conditions ------------------------------------------------------------------------------------------------


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT)
    except OSError:
        return "unknown"
    return out.stdout.strip() or "uncommitted"


def git_untracked(files: list[Path]) -> list[str] | None:
    """Files the run loads that are not in the commit, plus untracked files under src/ (importable code).
    None if git is unavailable."""
    inside = [f for f in files if f.resolve().is_relative_to(ROOT)]
    outside = [f.as_posix() for f in files if f not in inside]
    names = sorted({rel(f) for f in inside})
    try:
        tracked = subprocess.run(["git", "ls-files", "--", *names], capture_output=True, text=True, cwd=ROOT)
        new_src = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", "src"], capture_output=True, text=True, cwd=ROOT
        )
    except OSError:
        return None
    if tracked.returncode != 0 or new_src.returncode != 0:
        return None
    known = set(tracked.stdout.splitlines())
    return sorted({*outside, *(n for n in names if n not in known), *new_src.stdout.splitlines()})


def loaded_files(cases: Path, prompts: dict, search_info: dict) -> list[Path]:
    """Every file whose content shapes the numbers of this run."""
    files = [Path(__file__), ROOT / "scripts" / "run_baseline.py", SEED, ROOT / PRICES_PATH]
    files += [jsoncall.PROMPTS_DIR / f"{v}.md" for v in prompts.values()]
    files.append(sha256_file(cases) if sha256_file(cases).exists() else cases)  # held-out: only the hash is committed
    if search_info.get("chunks_path"):
        files.append(ROOT / search_info["chunks_path"])
    return files


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def default_prompts() -> dict:
    """The prompt versions the pipeline code uses when run_case is given none."""
    return {
        "classifier": classifier.PROMPT_VERSION,
        "extract": extract_step.PROMPT_VERSION,
        "answer": answer_step.ANSWER_PROMPT,
        "lookup": answer_step.LOOKUP_PROMPT,
    }


def parse_prompts(text: str) -> dict:
    steps = default_prompts()
    out = {}
    for part in (p.strip() for p in text.split(",") if p.strip()):
        step, sep, version = part.partition("=")
        step, version = step.strip(), version.strip()
        if not sep or step not in steps:
            raise ValueError(f"--prompts: expected step=version with step in {', '.join(steps)}, got {part!r}")
        if not (jsoncall.PROMPTS_DIR / f"{version}.md").exists():
            raise ValueError(f"--prompts: no prompts/{version}.md")
        out[step] = version
    return out


def run_case_accepts_prompts() -> bool:
    return "prompts" in inspect.signature(run_case).parameters


def load_table(kind: str) -> tuple[DeadlineTable, dict]:
    rows = [json.loads(line) for line in SEED.read_text(encoding="utf-8").splitlines() if line.strip()]
    from_docs = [r for r in rows if r.get("origin") and (CORPUS_DIR / f"{r['origin']}.md").exists()]
    kept = rows if kind == "seed" else from_docs
    info = {
        "source": kind,
        "path": rel(SEED),
        "sha256": lf_sha256(SEED),
        "rows": len(kept),
        "rows_from_cases": sum(1 for r in kept if r not in from_docs),
    }
    return DeadlineTable(kept), info


def load_search(kind: str) -> tuple[Callable, dict]:
    if kind == "stub":
        info = {"backend": "stub", "chunks_sha256": None, "n_chunks": None, "embedding_model": None}
        return search_stub.search, {**info, "reranker_model": None}
    from aic390.rag import search as rag  # needs the [rag] extra; CI never gets here

    lines = [line for line in rag.DEFAULT_CHUNKS.read_text(encoding="utf-8").splitlines() if line.strip()]
    info = {
        "backend": "real",
        "chunks_path": rel(rag.DEFAULT_CHUNKS),
        "chunks_sha256": lf_sha256(rag.DEFAULT_CHUNKS),
        "n_chunks": len(lines),
        "embedding_model": rag.EMBEDDING_MODEL,
        "reranker_model": rag.RERANKER_MODEL,
    }
    return rag.search, info


def conditions_text(config: dict) -> str:
    s, t = config["search"], config["table"]
    search = (
        "stub search"
        if s["backend"] == "stub"
        else f"real search ({s['n_chunks']} chunks, {s['embedding_model']} + {s['reranker_model']})"
    )
    table = "seed table with expected rows" if t["rows_from_cases"] else "docs-only table (no expected rows)"
    prompts = ", ".join(f"{k}={v}" for k, v in config["prompts"].items())
    return f"{search}, {table}, prompts {prompts}, model {config['model']['requested']}, T={config['temperature']}"


# Grading -------------------------------------------------------------------------------------------------------


def _row_key(row: dict) -> tuple:
    return row.get("course"), row.get("item_key")


def _candidates(candidates: list | None) -> list[str]:
    return sorted(json.dumps(c, sort_keys=True) for c in candidates or [])


def grade_deadlines(expected: list[dict], output: list[dict]) -> bool:
    """Rows match on (course, item_key); a missing, extra or duplicate row fails. `item` is not graded."""
    exp = {_row_key(r): r for r in expected}
    out = {_row_key(r): r for r in output}
    if len(exp) != len(expected) or len(out) != len(output) or exp.keys() != out.keys():
        return False
    for key, e in exp.items():
        o = out[key]
        if any(o.get(f) != e.get(f) for f in ROW_FIELDS):
            return False
        if _candidates(o.get("due_candidates")) != _candidates(e.get("due_candidates")):
            return False
    return True


def grade_sources(expected: list[dict], output: list[dict]) -> tuple[bool, int]:
    """Every expected {doc_id, section} must be cited; extra sources are allowed and counted."""
    exp = {(s.get("doc_id"), s.get("section")) for s in expected}
    out = {(s.get("doc_id"), s.get("section")) for s in output}
    return exp <= out, len(out - exp)


def grade_action(expected: dict | None, output: dict | None) -> bool:
    if expected is None or output is None:
        return expected is None and output is None
    return all(output.get(f) == expected.get(f) for f in ACTION_FIELDS)


def grade(expected: dict, output: dict) -> tuple[dict, int]:
    """{field: True | False | None} in CODE_FIELDS + JUDGE_FIELDS order, and the number of extra sources."""
    sources_ok, extra = grade_sources(expected.get("sources") or [], output.get("sources") or [])
    fields = {}
    for field in CODE_FIELDS:
        if field in EXACT_FIELDS:
            fields[field] = output.get(field) == expected.get(field)
        elif field == "deadlines":
            fields[field] = grade_deadlines(expected.get("deadlines") or [], output.get("deadlines") or [])
        elif field == "sources":
            fields[field] = sources_ok
        elif field == "action":
            fields[field] = grade_action(expected.get("action"), output.get("action"))
        elif field == "answer_language":
            want = expected.get("answer_language")
            fields[field] = None if want is None else output.get("answer_language") == want
    fields.update({f: None for f in JUDGE_FIELDS})
    return fields, extra


def failed_fields() -> dict:
    """Field results for a case whose run_case raised: no output to grade, so every field is null. The case is
    still incorrect (through `error`), but the per-field results do not blame any field for the crash."""
    return {f: None for f in (*CODE_FIELDS, *JUDGE_FIELDS)}


def is_correct(fields: dict) -> bool:
    return all(v for v in fields.values() if v is not None)


# Running -------------------------------------------------------------------------------------------------------


def run_cases(
    cases: list[dict],
    client: CountingClient,
    search: Callable,
    table: DeadlineTable,
    prompts: dict | None = None,
    on_record: Callable[[dict], None] | None = None,
) -> list[dict]:
    records = []
    for case in cases:
        first_call, slept_before = len(client.calls), client.slept_s
        start = time.perf_counter()
        output, error = None, None
        kwargs = {"search": search, "table": table}
        if prompts is not None:
            kwargs["prompts"] = prompts
        try:
            output = run_case(case, client, **kwargs)
        except Exception as exc:  # recorded as an incorrect case; the run continues
            error = repr(exc)
        calls = client.calls[first_call:]
        waited = client.slept_s - slept_before + sum(c["retry_wait_s"] for c in calls)
        latency = time.perf_counter() - start - waited
        if output is not None:
            fields, extra = grade(case["expected"], output)
        else:
            fields, extra = failed_fields(), 0
        record = {
            "id": case["id"],
            "split": case.get("split"),
            "type": case.get("type"),
            "correct": error is None and is_correct(fields),
            "fields": fields,
            "extra_sources": extra,
            "error": error,
            "latency_s": latency,
            "calls": calls,
            "output": output,
            "expected": case["expected"],
        }
        records.append(record)
        if on_record is not None:
            on_record(record)
    return records


# Summary -------------------------------------------------------------------------------------------------------


def proportion(k: int, n: int) -> dict:
    """k/n with the Wilson 95% interval (scoreboard) and the handbook's normal interval beside it."""
    if n == 0:
        return {"k": 0, "n": 0, "value": None, "ci95_wilson": None, "ci95_normal": None}
    wilson = proportion_ci(k, n, method="wilson")
    normal = proportion_ci(k, n, method="normal")
    return {
        "k": k,
        "n": n,
        "value": round(k / n, 4),
        "ci95_wilson": [round(x, 4) for x in wilson],
        "ci95_normal": [round(x, 4) for x in normal],
    }


def _abstained(record: dict) -> bool:
    return bool(record["output"] and record["output"].get("abstain"))


def _accuracy(records: list[dict]) -> dict:
    return proportion(sum(r["correct"] for r in records), len(records))


def reporting_problems(config: dict, complete: bool, prompt_mismatches: list[str]) -> list[str]:
    problems = []
    if config["dry_run"]:
        problems.append("dry run with the offline fake model")
    if not config["frozen"]:
        problems.append("test set does not match its recorded sha256 (--unfrozen)")
    if config["dirty"] is None or config.get("untracked", []) is None:
        problems.append("git state unknown")
    if config["dirty"]:
        problems.append("uncommitted changes: " + ", ".join(config["dirty"]))
    if config.get("untracked"):
        problems.append("not in the commit: " + ", ".join(config["untracked"]))
    if config["subset"]:
        problems.append("subset of the test set (--ids / --limit)")
    if not complete:
        problems.append("run did not finish")
    problems += [f"prompt version differs from config: {m}" for m in prompt_mismatches]
    return problems


def prompt_mismatches(records: list[dict], prompts: dict) -> list[str]:
    seen = {
        (t.get("step"), t.get("prompt_version")) for r in records if r["output"] for t in r["output"].get("trace", [])
    }
    return sorted(f"{step} ran {v}, recorded {prompts.get(step)}" for step, v in seen if prompts.get(step) != v)


def summarize(records: list[dict], config: dict, prices: dict | None, complete: bool = True) -> dict:
    n = len(records)
    calls = [c for r in records for c in r["calls"]]
    model = config["model"]["requested"]
    price = (prices or {}).get(model)
    cost_total = (
        sum(request_cost(model, c["input_tokens"], c["output_tokens"], {model: price}) for c in calls)
        if price is not None
        else None
    )
    mismatches = prompt_mismatches(records, config["prompts"])
    problems = reporting_problems(config, complete, mismatches)
    unanswerable = [r for r in records if r["type"] == "unanswerable"]
    adversarial = [r for r in records if r["type"] == "adversarial" and r["expected"].get("abstain")]
    answerable = [r for r in records if not r["expected"].get("abstain")]
    per_field = {}
    for field in CODE_FIELDS:
        graded = [r["fields"][field] for r in records if r["fields"][field] is not None]
        per_field[field] = proportion(sum(graded), len(graded))
    per_field.update({f: "not graded (W2.6 judge)" for f in JUDGE_FIELDS})
    return {
        "for_reporting": not problems,
        "not_for_reporting_reasons": problems,
        "complete": complete,
        "conditions": conditions_text(config),
        "correct_rule": CORRECT_RULE,
        "n": n,
        "correct": sum(r["correct"] for r in records),
        "accuracy": _accuracy(records),
        "by_split": {s: _accuracy([r for r in records if r["split"] == s]) for s in ("seen", "new")},
        "by_type": {
            t: _accuracy([r for r in records if str(r["type"]) == t]) for t in sorted({str(r["type"]) for r in records})
        },
        "per_field": per_field,
        "abstention_correct": proportion(sum(map(_abstained, unanswerable)), len(unanswerable)),
        "adversarial_refusal": proportion(sum(map(_abstained, adversarial)), len(adversarial)),
        "false_abstentions": proportion(sum(map(_abstained, answerable)), len(answerable)),
        "definitions": DEFINITIONS,
        "failed": [
            {"id": r["id"], "fields": [f for f, v in r["fields"].items() if v is False], "error": r["error"]}
            for r in records
            if not r["correct"]
        ],
        "errors": sum(r["error"] is not None for r in records),
        "invalid_model_outputs": sum(1 for r in records if r["output"] and not r["output"].get("valid", True)),
        "extra_sources_total": sum(r["extra_sources"] for r in records),
        "n_calls": len(calls),
        "call_errors": sum(c["error"] is not None for c in calls),
        "rate_limit_retries": sum(c["retries"] for c in calls),
        "rate_limit_wait_s": round(sum(c["retry_wait_s"] for c in calls), 3),
        "input_tokens": sum(c["input_tokens"] for c in calls),
        "output_tokens": sum(c["output_tokens"] for c in calls),
        "latency_p50_s": round(statistics.median(r["latency_s"] for r in records), 3) if n else None,
        "latency_definition": LATENCY_DEFINITION,
        "cost_usd_at_list_price": round(cost_total, 6) if cost_total is not None else None,
        "cost_per_case_usd_at_list_price": round(cost_total / n, 6) if cost_total is not None and n else None,
        "spend_usd": 0.0,
        "spend_basis": "dry run: offline fake model" if config["dry_run"] else "free plan (D-006): no charge",
        "wall_time_s": config.get("wall_time_s"),
    }


def _fmt(p: dict) -> str:
    if p["n"] == 0:
        return "n = 0"
    w, nm = p["ci95_wilson"], p["ci95_normal"]
    wilson, normal = f"[{w[0]:.3f}, {w[1]:.3f}]", f"[{nm[0]:.3f}, {nm[1]:.3f}]"
    return f"{p['k']}/{p['n']} = {p['value']:.3f}, Wilson 95% {wilson}, normal {normal}"


def summary_markdown(summary: dict, config: dict) -> str:
    lines = []
    if not summary["for_reporting"]:
        lines += ["**NOT FOR REPORTING**: " + "; ".join(summary["not_for_reporting_reasons"]), ""]
    lines += [
        f"# e2e run `{config['label']}`",
        "",
        f"Conditions: {summary['conditions']}.",
        f"Test set: `{config['cases_path']}` (sha256 `{config['cases_sha256']}`, split {config['split_filter']}).",
        f"Commit `{config['commit']}`; script `{SCRIPT}`.",
        "",
        f"**Accuracy: {_fmt(summary['accuracy'])}**. Rule: {summary['correct_rule']}.",
        "",
        "| Group | Accuracy |",
        "|---|---|",
    ]
    lines += [f"| split {k} | {_fmt(v)} |" for k, v in summary["by_split"].items()]
    lines += [f"| type {k} | {_fmt(v)} |" for k, v in summary["by_type"].items()]
    lines += ["", "| Field | Correct |", "|---|---|"]
    lines += [f"| {k} | {v if isinstance(v, str) else _fmt(v)} |" for k, v in summary["per_field"].items()]
    lines += ["", "| Refusal metric | Value | Definition |", "|---|---|---|"]
    lines += [f"| {k} | {_fmt(summary[k])} | {d} |" for k, d in summary["definitions"].items()]
    lines += ["", "Failed cases:", ""]
    lines += [
        f"- {f['id']}: {', '.join(f['fields'])}" + (f" (error: {f['error']})" if f["error"] else "")
        for f in summary["failed"]
    ] or ["- none"]
    cost = summary["cost_per_case_usd_at_list_price"]
    lines += [
        "",
        f"Calls {summary['n_calls']} ({summary['call_errors']} failed, {summary['rate_limit_retries']} rate-limit "
        f"retries); tokens in {summary['input_tokens']}, out {summary['output_tokens']}; "
        f"latency p50 per case {summary['latency_p50_s']} s ({summary['latency_definition']}); "
        f"wall time {summary['wall_time_s']} s.",
        f"Cost per case at list price: {cost if cost is not None else 'null (no price)'} USD; "
        f"actual spend {summary['spend_usd']} USD ({summary['spend_basis']}).",
        f"Extra sources cited (allowed): {summary['extra_sources_total']}. Errors: {summary['errors']}. "
        f"Invalid model outputs: {summary['invalid_model_outputs']}.",
    ]
    return "\n".join(lines) + "\n"


def spend_total(previous: dict | None, run_spend: float, week: int) -> float | None:
    """The previous board's total plus this run's spend. Rewriting a board of the same week replaces that week's
    spend instead of adding it twice. Null when the previous total is unknown."""
    if previous is None or previous.get("spend_total_usd") is None:
        return None
    base = previous["spend_total_usd"]
    if previous.get("week") == week:
        base -= previous.get("spend_week_usd") or 0
    return round(base + run_spend, 6)


def scoreboard_from(summary: dict, config: dict, previous: dict | None = None, week: int = 2) -> dict:
    """Scoreboard for `week`: only what this run measured, plus the running spend total from the previous board;
    every other key stays null."""
    if not summary["for_reporting"]:
        raise ValueError("refusing --write-scoreboard: " + "; ".join(summary["not_for_reporting_reasons"]))
    board = empty_scoreboard(week=week, test_set_size=summary["n"])
    for key in ("e2e_accuracy", "abstention_correct"):
        p = summary["accuracy" if key == "e2e_accuracy" else key]
        if p["n"]:
            board[key] = {
                "value": round(p["value"], 3),
                "ci95": [round(x, 3) for x in p["ci95_wilson"]],
                "n": p["n"],
                "script": SCRIPT,
            }
    board["cost_per_task_usd"] = summary["cost_per_case_usd_at_list_price"]
    board["latency_p50_s"] = summary["latency_p50_s"]
    board["spend_week_usd"] = summary["spend_usd"]
    board["spend_total_usd"] = spend_total(previous, summary["spend_usd"], board["week"])
    return board


# Command line --------------------------------------------------------------------------------------------------


def _ids(text: str) -> list[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="JSONL test set (default: week2_cases.jsonl)")
    ap.add_argument("--split", choices=("seen", "new", "all"), default="all", help="filter on the split field")
    ap.add_argument("--ids", type=_ids, default=None, help="comma-separated case ids (smoke test)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N selected cases (smoke test)")
    ap.add_argument("--search", choices=("stub", "real"), default="stub", help="real = aic390.rag.search.search")
    ap.add_argument(
        "--table",
        choices=("seed", "docs-only"),
        default="seed",
        help="docs-only drops the seed rows created from test cases",
    )
    ap.add_argument("--prompts", default=None, help="step=version,... e.g. extract=extract_v2,answer=answer_v1")
    ap.add_argument("--label", default="run", help="part of the results folder name")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between model calls (free-plan rate limit)")
    ap.add_argument("--yes", action="store_true", help="skip the paid-call budget prompt")
    ap.add_argument("--dry-run", action="store_true", help="offline fake model, free")
    ap.add_argument("--unfrozen", action="store_true", help="run a test set that does not match its sha256")
    ap.add_argument("--allow-dirty", action="store_true", help="real run with uncommitted changes")
    ap.add_argument("--write-scoreboard", action="store_true", help="write eval/scoreboard.json from this run")
    return ap


def fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")  # a Windows code page cannot print every character
    args = build_parser().parse_args(argv)
    cases_path: Path = args.cases

    if not cases_path.exists():
        return fail(f"no such cases file: {cases_path}")
    actual = lf_sha256(cases_path)
    recorded = recorded_sha256(cases_path)
    frozen = recorded is not None and recorded == actual
    if not frozen and not args.unfrozen:
        why = "no recorded sha256" if recorded is None else f"sha256 {actual} differs from the recorded {recorded}"
        return fail(f"{rel(cases_path)} is not frozen ({why}); pass --unfrozen to run it anyway (not for reporting)")

    try:
        cases = load_inputs(cases_path)
        missing = [c["id"] for c in cases if "expected" not in c]
        if missing:
            raise ValueError(f"cases without 'expected': {', '.join(missing)}")
        cases = [c for c in cases if args.split == "all" or c.get("split") == args.split]
        cases = select_inputs(cases, args.ids, args.limit)
    except ValueError as exc:
        if sha256_file(cases_path).exists():  # held-out set: never echo its text
            return fail(f"{rel(cases_path)} has a malformed line or an unknown id (held-out: details not shown)")
        return fail(str(exc))
    if not cases:
        return fail("no cases selected")

    prompts = default_prompts()
    prompts_arg = None
    if args.prompts is not None:
        if not run_case_accepts_prompts():
            return fail("--prompts given, but run_case(case, client, search, table) has no 'prompts' parameter yet")
        try:
            prompts_arg = {**prompts, **parse_prompts(args.prompts)}
        except ValueError as exc:
            return fail(str(exc))
        prompts = prompts_arg

    search, search_info = load_search(args.search)
    table, table_info = load_table(args.table)
    dirty = git_dirty_files(DIRTY_PATHS, cwd=ROOT)
    untracked = git_untracked(loaded_files(cases_path, prompts, search_info))
    clean = dirty == [] and untracked == []
    if not args.dry_run and not clean and not args.allow_dirty:
        if dirty is None or untracked is None:
            state = "git state unknown"
        else:
            parts = [("uncommitted changes", dirty), ("not in the commit", untracked)]
            state = "; ".join(f"{what}: {', '.join(files)}" for what, files in parts if files)
        return fail(f"{state}; commit first (R8) or pass --allow-dirty (not for reporting)")
    subset = args.ids is not None or args.limit is not None or args.split != "all"
    if args.write_scoreboard and (args.dry_run or not frozen or not clean or subset):
        return fail("--write-scoreboard needs a full real run (all cases) on a frozen test set and a clean tree")

    client = CountingClient(FakeClient() if args.dry_run else OpenAICompatibleClient(), sleep_s=args.sleep)
    prices = None if args.dry_run else load_prices(ROOT / PRICES_PATH)

    estimate = ESTIMATED_CALLS_PER_CASE * len(cases)
    if not args.dry_run:
        price = (prices or {}).get(client.model)
        if price is not None:
            per_call = request_cost(client.model, *ESTIMATED_TOKENS_PER_CALL, {client.model: price})
            cost = f"~{estimate * per_call:.4f} USD at list price (estimate: {ESTIMATED_TOKENS_PER_CALL} tokens/call)"
        else:
            cost = "no list price in config/prices.json"
        print(
            f"{len(cases)} cases, ~{estimate} calls (up to {2 * estimate} with retries) to {client.model}; {cost}; "
            "actual spend on the free plan 0 USD."
        )
        if estimate > BUDGET_WITHOUT_ASKING and not args.yes:
            if input("Continue? [y/N] ").strip().lower() != "y":
                return 1

    label = re.sub(r"[^A-Za-z0-9._-]+", "-", args.label).strip("-") or "run"
    out = RESULTS_DIR / f"{date.today().isoformat()}_e2e_{label}_{client.model.replace('/', '-')}"
    outputs_path = out / "outputs.jsonl"
    if outputs_path.exists() and outputs_path.stat().st_size > 0:
        return fail(f"{outputs_path} already has results; use another --label")
    out.mkdir(parents=True, exist_ok=True)

    config = {
        "commit": git_commit(),
        "dirty": dirty,
        "untracked": untracked,
        "harness_sha256": lf_sha256(Path(__file__)),
        "model": {"requested": client.model, "returned": []},
        "temperature": jsoncall.TEMPERATURE,
        "prompts": prompts,
        "cases_path": rel(cases_path),
        "cases_sha256": actual,
        "frozen": frozen,
        "split_filter": args.split,
        "ids": [c["id"] for c in cases],
        "subset": args.ids is not None or args.limit is not None,
        "n": len(cases),
        "search": search_info,
        "table": table_info,
        "judge_fields": "not graded",
        "started_at": now(),
        "finished_at": None,
        "wall_time_s": None,
        "n_calls": 0,
        "sleep_s": args.sleep,
        "argv": [SCRIPT, *argv],
        "label": label,
        "dry_run": args.dry_run,
        "script": SCRIPT,
    }

    def write_config() -> None:
        (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    write_config()
    if args.search == "real":
        search("warm-up", k=1)  # loads both models and builds the index outside the per-case timer
    records: list[dict] = []
    complete = False
    start = time.perf_counter()
    try:
        with outputs_path.open("w", encoding="utf-8") as f:

            def append(record: dict) -> None:
                records.append(record)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()

            run_cases(cases, client, search, table, prompts_arg, on_record=append)
        complete = True
    except KeyboardInterrupt:
        print("interrupted: writing the summary of the finished cases", file=sys.stderr)
    finally:
        config["finished_at"] = now()
        config["wall_time_s"] = round(time.perf_counter() - start, 1)
        config["n_calls"] = len(client.calls)
        config["model"]["returned"] = sorted({c["model"] for c in client.calls if c["model"]})
        write_config()
        summary = summarize(records, config, prices, complete)
        (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        markdown = summary_markdown(summary, config)
        (out / "summary.md").write_text(markdown, encoding="utf-8")

    print(markdown)
    print(f"wrote {rel(out)}")
    if not complete:
        return 130
    if args.write_scoreboard:
        try:
            board_path = ROOT / SCOREBOARD_PATH
            previous = json.loads(board_path.read_text(encoding="utf-8")) if board_path.exists() else None
            write_scoreboard(scoreboard_from(summary, config, previous), board_path)
        except ValueError as exc:
            return fail(str(exc))
        print("wrote eval/scoreboard.json")
    return 2 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
