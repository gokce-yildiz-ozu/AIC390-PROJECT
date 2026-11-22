"""W2.6 LLM judge for the prose fields `must_include[]` and `must_not[]`, checked against blind human labels.

    python eval/judge.py sheet                       # writes the 20-row labelling sheet; no model call
    python eval/judge.py run --sleep 13 --yes        # only after labels_human.csv is labelled and committed
    python eval/judge.py kappa                       # confusion matrix, agreement, Cohen's kappa
    python eval/judge.py run --dry-run --dir <tmp>   # offline fake judge, on a copy of a labelled sheet
    python eval/judge.py run --resume --sleep 13     # after a stopped run: judges only the missing rows

The order is enforced in code so the human labels stay blind: `run` refuses until every `human_pass` in
labels_human.csv is true or false and the file is committed and unchanged; it records the file's sha256 and commit,
and never prints a verdict. A real run reads only a sheet under results/ in this repository. `kappa` refuses if the
labels changed after the run.

Labelling: edit labels_human.csv as UTF-8 with comma separators (VS Code or LibreOffice). A spreadsheet program set
to a Turkish locale may save it with ";" or in another encoding; `run` then refuses the file.

Label unit: one answer. pass = the answer says every must_include item (meaning, not exact words) and none of the
must_not items. The model judges each criterion; this code computes pass from the items. A reply that is invalid
twice gives judge_pass null, which counts as a disagreement with the human label. A failed API call or a reply
from another model stops the run instead (no row is recorded for it); `--resume` finishes it.

Answers (no new ones are generated): the T = 0 baseline answers of the 9 week-1 cases with judge criteria, and 11
answers of the v1 e2e run drawn with random.Random(0).sample from the 18 cases with judge criteria (file order).
Criteria always come from `expected` in week2_cases.jsonl.
"""

import argparse
import csv
import json
import random
import re
import subprocess
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from aic390 import jsoncall
from aic390.llm import ChatClient, FakeClient, LLMResponse, OpenAICompatibleClient
from aic390.stats import cohen_kappa, kappa_bootstrap_ci, proportion_ci

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
from run_e2e import (  # noqa: E402
    BUDGET_WITHOUT_ASKING,
    CountingClient,
    git_commit,
    git_dirty_files,
    git_untracked,
    lf_sha256,
    rel,
)

SCRIPT = "eval/judge.py"
RESULTS_DIR = ROOT / "results"  # where the judge folder goes
REPO = ROOT  # the git repository the labelled sheet must be committed in
SOURCES_DIR = ROOT / "results"  # the two runs the answers come from
CASES = ROOT / "eval" / "testsets" / "week2_cases.jsonl"
BASELINE_RUN = "2026-11-16_baseline_openai-gpt-oss-120b"
V1_RUN = "2026-11-22_e2e_v1-stub-seed_openai-gpt-oss-120b"
BASELINE_IDS = ("w1-09", "w1-10", "w1-11", "w1-12", "w1-13", "w1-16", "w1-19", "w1-21", "w1-22")
V1_SAMPLE_N = 11
SAMPLE_SEED = 0
FOLDER_SUFFIX = "_judge-v1"
LABELS = "labels_human.csv"
OUTPUTS = "judge_outputs.jsonl"
COLUMNS = ("id", "source_run", "question", "answer", "must_include", "must_not", "human_pass", "human_note")
JUDGE_MODEL = "qwen/qwen3.8-27b"  # D-006: a different family from the main model
PROMPT_VERSION = "judge_v1"
TEMPERATURE = 0.0
USER_SPLIT = "\n---USER---\n"
DIRTY_PATHS = ("src", "prompts", "eval", "scripts")
HOW_TO_LABEL = "human_pass: true or false; edit as UTF-8 with comma separators (VS Code or LibreOffice)"
INVALID_RULE = (
    "an invalid judge row (judge_pass null) counts as a disagreement: it takes the opposite of the human label, "
    "which also shifts the judge's class rates used in kappa's expected agreement"
)
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0
KAPPA_PLAN_THRESHOLD = 0.6  # docs/STATUS.md, Experiments plan row for W2.6
CRITERIA_SEPARATOR = " | "  # in the sheet only; the run reads criteria from week2_cases.jsonl

# The invented example of prompts/judge_v1.md, sent once before the 20 rows to check that the provider serves
# the judge model.
SMOKE = {
    "question": "BIO-204 final sınavına giremezsem ne yapmalıyım?",
    "answer": (
        "BIO-204 izlencesine göre final sınavına giremeyen öğrencinin doktor raporu gibi bir mazeret belgesi sunması "
        "gerekir [1]. Mazeret sınavı 15 Ocak'ta yapılacak."
    ),
    "must_include": ["mazeret belgesi gerektiği", "bölüm sekreterliğine başvurulduğu"],
    "must_not": ["mazeret sınavı tarihini kesin olarak vermek"],
}


# Sheet ---------------------------------------------------------------------------------------------------------


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def has_criteria(case: dict) -> bool:
    exp = case["expected"]
    return bool(exp.get("must_include") or exp.get("must_not"))


def sample_v1_ids(cases: list[dict]) -> list[str]:
    return random.Random(SAMPLE_SEED).sample([c["id"] for c in cases if has_criteria(c)], V1_SAMPLE_N)


def build_rows(results_dir: Path = SOURCES_DIR, cases_path: Path = CASES) -> tuple[list[dict], dict]:
    """The 20 sheet rows (without labels) and the provenance written to sheet.json. Raises ValueError when a
    source does not match week2_cases.jsonl."""
    cases = load_jsonl(cases_path)
    by_id = {c["id"]: c for c in cases}
    cases_sha = lf_sha256(cases_path)

    base_dir = results_dir / BASELINE_RUN
    base_config = json.loads((base_dir / "config.json").read_text(encoding="utf-8"))
    base_inputs_path = ROOT / Path(base_config["inputs"].replace("\\", "/"))
    base_inputs = {r["id"]: r for r in load_jsonl(base_inputs_path)}
    t0 = {r["id"]: r for r in load_jsonl(base_dir / "outputs.jsonl") if r["temperature"] == 0.0}

    v1_dir = results_dir / V1_RUN
    v1_config = json.loads((v1_dir / "config.json").read_text(encoding="utf-8"))
    if v1_config["cases_sha256"] != cases_sha:
        raise ValueError(f"{V1_RUN} ran a test set with sha256 {v1_config['cases_sha256']}, not {rel(cases_path)}")
    v1 = {r["id"]: r for r in load_jsonl(v1_dir / "outputs.jsonl")}

    rows = []
    for case_id in BASELINE_IDS:
        case = by_id[case_id]
        if not has_criteria(case):
            raise ValueError(f"{case_id} has no judge criteria in {rel(cases_path)}")
        if base_inputs[case_id]["text"] != case["text"]:
            raise ValueError(f"{case_id}: baseline input text differs from {rel(cases_path)}")
        record = t0[case_id]
        if record.get("error") or not record.get("text"):
            raise ValueError(f"{case_id}: the T = 0 baseline record has no answer")
        rows.append(_row(case, BASELINE_RUN, record["text"]))
    v1_ids = sample_v1_ids(cases)
    for case_id in v1_ids:
        record = v1[case_id]
        answer = (record.get("output") or {}).get("answer_text")
        if record.get("error") or not answer:
            raise ValueError(f"{case_id}: the v1 record has no answer_text")
        rows.append(_row(by_id[case_id], V1_RUN, answer))

    provenance = {
        "cases_path": rel(cases_path),
        "cases_sha256": cases_sha,
        "baseline": {
            "run": BASELINE_RUN,
            "outputs_sha256": lf_sha256(base_dir / "outputs.jsonl"),
            "inputs_path": rel(base_inputs_path),
            "temperature": 0.0,
            "ids": list(BASELINE_IDS),
        },
        "v1": {
            "run": V1_RUN,
            "outputs_sha256": lf_sha256(v1_dir / "outputs.jsonl"),
            "sample": f"random.Random({SAMPLE_SEED}).sample(ids with judge criteria in file order, {V1_SAMPLE_N})",
            "ids": v1_ids,
        },
        "n": len(rows),
    }
    return rows, provenance


def _row(case: dict, source_run: str, answer: str) -> dict:
    exp = case["expected"]
    return {
        "id": case["id"],
        "source_run": source_run,
        "question": case["text"],
        "answer": answer,
        "must_include": list(exp.get("must_include") or []),
        "must_not": list(exp.get("must_not") or []),
    }


def write_sheet(rows: list[dict], path: Path) -> None:
    # utf-8-sig so a spreadsheet program opens the Turkish text correctly
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "must_include": CRITERIA_SEPARATOR.join(row["must_include"]),
                    "must_not": CRITERIA_SEPARATOR.join(row["must_not"]),
                    "human_pass": "",
                    "human_note": "",
                }
            )


# Labels --------------------------------------------------------------------------------------------------------


def read_sheet(path: Path) -> list[dict]:
    """Raises ValueError when the file is not UTF-8 or not a comma-separated sheet with the expected columns."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            columns = tuple(reader.fieldnames or ())
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(f"{path.name} cannot be read ({exc}); {HOW_TO_LABEL}") from exc
    if columns != COLUMNS:
        raise ValueError(f"{path.name} has columns {list(columns)}, expected {list(COLUMNS)}; {HOW_TO_LABEL}")
    return rows


def parse_label(value: str | None) -> bool | None:
    text = (value or "").strip().lower()
    return {"true": True, "false": False}.get(text)


def _squash(text: str) -> str:
    return " ".join((text or "").split())


def label_problems(sheet: list[dict], rows: list[dict]) -> list[str]:
    """Why the labelled sheet cannot be used: rows that differ from the rebuilt sheet, or a human_pass that is not
    true or false. Says which rows, never which value."""
    problems = []
    if [(r.get("id"), r.get("source_run")) for r in sheet] != [(r["id"], r["source_run"]) for r in rows]:
        return ["rows (id, source_run) differ from the sheet that `sheet` builds"]
    changed = [r["id"] for r, s in zip(rows, sheet, strict=True) if _squash(s.get("answer")) != _squash(r["answer"])]
    if changed:
        problems.append("answer text changed in rows: " + ", ".join(changed))
    empty = [f"{i} ({s['id']})" for i, s in enumerate(sheet, start=1) if parse_label(s.get("human_pass")) is None]
    if empty:
        problems.append("human_pass is not true or false in rows: " + ", ".join(empty))
    return problems


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd)
    except OSError:
        return None


def labels_git_state(path: Path, repo: Path | None = None) -> tuple[str | None, str | None]:
    """(problem, commit): problem is None when the file is tracked in `repo` (default: this repository) and has no
    uncommitted change; commit is the last commit that touched it."""
    cwd = repo or REPO
    if not is_inside(path, cwd):
        return f"{path.as_posix()} is outside the repository", None
    name = path.resolve().relative_to(cwd.resolve()).as_posix()
    tracked = _git(["ls-files", "--error-unmatch", "--", name], cwd)
    if tracked is None:
        return "git is not available", None
    if tracked.returncode != 0:
        return f"{path.as_posix()} is not committed (untracked)", None
    status = _git(["status", "--porcelain", "--", name], cwd)
    if status is None or status.returncode != 0:
        return "git state unknown", None
    if status.stdout.strip():
        return f"{path.as_posix()} has uncommitted changes", None
    log = _git(["log", "-1", "--format=%h", "--", name], cwd)
    return None, (log.stdout.strip() if log and log.returncode == 0 else None)


# Judging -------------------------------------------------------------------------------------------------------


class JudgeItem(BaseModel):
    criterion: str
    type: Literal["must_include", "must_not"]
    met: bool
    evidence: str


class JudgeReply(BaseModel):
    items: list[JudgeItem]


def load_judge_prompt(version: str = PROMPT_VERSION) -> tuple[str, str]:
    system, sep, user = jsoncall.load_prompt(version).partition(USER_SPLIT)
    if not sep:
        raise ValueError(f"prompts/{version}.md has no {USER_SPLIT.strip()} line")
    return system.strip(), user.strip()


def criteria_list(must_include: list[str], must_not: list[str]) -> list[dict]:
    return [{"criterion": c, "type": "must_include"} for c in must_include] + [
        {"criterion": c, "type": "must_not"} for c in must_not
    ]


def user_message(template: str, question: str, answer: str, criteria: list[dict]) -> str:
    # str.replace, not str.format: the criteria are JSON with braces
    return (
        template.replace("{question}", question)
        .replace("{criteria}", json.dumps(criteria, ensure_ascii=False))
        .replace("{answer}", answer)
    )


def _key(criterion: str, kind: str) -> tuple[str, str]:
    """Criteria match after case folding and with punctuation and spacing ignored, so a reply that changes a quote
    mark or a trailing period still matches; letters, digits and % must be the same."""
    text = unicodedata.normalize("NFKD", criterion).casefold()
    kept = "".join(ch if ch.isalnum() or ch == "%" else " " for ch in text if not unicodedata.combining(ch))
    return kind, " ".join(kept.split())


def parse_reply(text: str, criteria: list[dict]) -> list[dict]:
    """Validated items, one per criterion. Raises ValueError when the JSON is invalid or a criterion is missing,
    duplicated or unknown."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)  # reasoning models may prefix their thinking
    reply = jsoncall.parse_json(text, JudgeReply)
    want = [_key(c["criterion"], c["type"]) for c in criteria]
    got = [_key(i.criterion, i.type) for i in reply.items]
    missing = [k[1] for k in want if k not in got]
    duplicated = sorted({k[1] for k in got if got.count(k) > 1})
    unknown = [k[1] for k in got if k not in want]
    problems = [
        f"{what}: {', '.join(repr(x) for x in names)}"
        for what, names in (("missing", missing), ("duplicated", duplicated), ("unknown", unknown))
        if names
    ]
    if problems:
        raise ValueError("criteria " + "; ".join(problems))
    by_key = {_key(i.criterion, i.type): i for i in reply.items}
    return [{**c, "met": by_key[k].met, "evidence": by_key[k].evidence} for c, k in zip(criteria, want, strict=True)]


def verdict(items: list[dict]) -> bool:
    """pass = every must_include item met and no must_not item met."""
    return all(i["met"] for i in items if i["type"] == "must_include") and not any(
        i["met"] for i in items if i["type"] == "must_not"
    )


def judge_answer(
    client: ChatClient, system: str, template: str, question: str, answer: str, must_include, must_not
) -> dict:
    """One answer: the first call plus one retry on an invalid reply. A failed API call is not retried here (the
    client already retries rate limits)."""
    criteria = criteria_list(must_include, must_not)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message(template, question, answer, criteria)},
    ]
    attempts = []
    for attempt in range(1, jsoncall.MAX_ATTEMPTS + 1):
        resp = client.chat(messages, temperature=TEMPERATURE)
        record = {
            "attempt": attempt,
            "model": resp.model,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "latency_s": resp.latency_s,
            "api_error": resp.error,
            "invalid_reason": None,
            "reply": resp.text,
        }
        attempts.append(record)
        if resp.error is not None:
            break
        try:
            items = parse_reply(resp.text, criteria)
        except ValueError as exc:
            record["invalid_reason"] = str(exc)
            messages += [
                {"role": "assistant", "content": resp.text},
                {"role": "user", "content": f"Your reply was not valid ({exc}). Reply with the JSON object only."},
            ]
            continue
        return {"valid": True, "judge_pass": verdict(items), "items": items, "attempts": attempts}
    return {"valid": False, "judge_pass": None, "items": None, "attempts": attempts}


class DryRunJudgeClient(FakeClient):
    """Offline judge for --dry-run: reads the criteria from the user message and marks every must_include met and
    every must_not not met. Says nothing about real answers."""

    def __init__(self, model: str = "fake-judge"):
        super().__init__(model)

    def chat(self, messages: list[dict], temperature: float) -> LLMResponse:
        user = next(m["content"] for m in messages if m["role"] == "user")
        line = next(x for x in user.splitlines() if x.startswith("Criteria: "))
        criteria = json.loads(line.removeprefix("Criteria: "))
        items = [{**c, "met": c["type"] == "must_include", "evidence": ""} for c in criteria]
        prompt = " ".join(m["content"] for m in messages)
        return LLMResponse(
            text=json.dumps({"items": items}, ensure_ascii=False),
            model=self.model,
            input_tokens=len(prompt) // 4,
            output_tokens=12,
            latency_s=0.0,
            model_requested=self.model,
        )


# Kappa ---------------------------------------------------------------------------------------------------------


def judge_reason(record: dict) -> str:
    if not record["valid"]:
        errors = [a["api_error"] or a["invalid_reason"] for a in record["attempts"]]
        return "invalid judge output (" + (errors[-1] if errors else "no reply") + "); counted as a disagreement"
    unmet = [i for i in record["items"] if i["type"] == "must_include" and not i["met"]]
    broken = [i for i in record["items"] if i["type"] == "must_not" and i["met"]]
    if not unmet and not broken:
        return "every must_include met, no must_not met"
    parts = [f"must_include not met: {i['criterion']!r}" for i in unmet]
    parts += [f"must_not met: {i['criterion']!r} (evidence: {i['evidence']!r})" for i in broken]
    return "; ".join(parts)


def proportion(k: int, n: int) -> dict:
    lo, hi = proportion_ci(k, n, method="wilson")
    return {"k": k, "n": n, "value": round(k / n, 4), "ci95_wilson": [round(lo, 4), round(hi, 4)]}


def kappa_report(sheet: list[dict], records: list[dict], config: dict) -> dict:
    by_key = {(r["id"], r["source_run"]): r for r in records}
    rows = []
    for s in sheet:
        record = by_key[(s["id"], s["source_run"])]
        rows.append({"id": s["id"], "source_run": s["source_run"], "human": parse_label(s["human_pass"]), **record})
    n = len(rows)
    human = [r["human"] for r in rows]
    # an invalid judge row counts as a disagreement: it takes the opposite of the human label
    judge = [(not r["human"]) if r["judge_pass"] is None else r["judge_pass"] for r in rows]
    agree = sum(h == j for h, j in zip(human, judge, strict=True))
    kappa = cohen_kappa(human, judge)
    lo, hi, undefined = kappa_bootstrap_ci(human, judge, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
    matrix = {
        f"human_{'pass' if h else 'fail'}": {
            f"judge_{name}": sum(1 for r in rows if r["human"] is h and r["judge_pass"] is j)
            for name, j in (("pass", True), ("fail", False), ("invalid", None))
        }
        for h in (True, False)
    }
    problems = list(config.get("not_for_reporting_reasons") or [])
    if not config.get("complete"):
        problems.append("judge run did not finish")
    if config["model"]["returned"] != [config["model"]["requested"]]:
        problems.append(f"models returned {config['model']['returned']}, requested {config['model']['requested']}")
    return {
        "for_reporting": not problems,
        "not_for_reporting_reasons": problems,
        "n": n,
        "confusion_matrix": matrix,
        "raw_agreement": proportion(agree, n),
        "cohen_kappa": None if kappa is None else round(kappa, 4),
        "kappa_ci95_bootstrap": None if lo is None else [round(lo, 4), round(hi, 4)],
        "bootstrap": {
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "unit": "answer (row), with replacement",
            "method": "percentile",
            "undefined_resamples": undefined,
        },
        "invalid_judge_rows": sum(r["judge_pass"] is None for r in rows),
        "call_errors": config.get("call_errors"),
        "invalid_rule": INVALID_RULE,
        "human_pass_rate": proportion(sum(human), n),
        "by_source_run": {
            run: {
                "n": sum(r["source_run"] == run for r in rows),
                "human_pass": sum(r["human"] for r in rows if r["source_run"] == run),
                "agree": sum(h == j for r, h, j in zip(rows, human, judge, strict=True) if r["source_run"] == run),
            }
            for run in (BASELINE_RUN, V1_RUN)
        },
        "disagreements": [
            {
                "id": r["id"],
                "source_run": r["source_run"],
                "human_pass": r["human"],
                "judge_pass": r["judge_pass"],
                "judge_reason": judge_reason(r),
            }
            for r, h, j in zip(rows, human, judge, strict=True)
            if h != j
        ],
        "plan_threshold": KAPPA_PLAN_THRESHOLD,
        "kappa_meets_plan_threshold": None if kappa is None else kappa >= KAPPA_PLAN_THRESHOLD,
        "conditions": conditions_text(config),
        "script": SCRIPT,
    }


def conditions_text(config: dict) -> str:
    returned = ", ".join(config["model"]["returned"]) or "none"
    return (
        f"commit {config['commit']}, judge model {config['model']['requested']} (returned: {returned}), "
        f"prompt {config['prompt_version']}, T={config['temperature']}, sheet sha256 {config['labels_sha256']} "
        f"(labels commit {config['labels_commit']})"
    )


def summary_markdown(report: dict) -> str:
    lines = []
    if not report["for_reporting"]:
        lines += ["**NOT FOR REPORTING**: " + "; ".join(report["not_for_reporting_reasons"]), ""]
    ra, hp, m = report["raw_agreement"], report["human_pass_rate"], report["confusion_matrix"]
    kappa = report["cohen_kappa"]
    ci = report["kappa_ci95_bootstrap"]
    b = report["bootstrap"]
    kappa_text = "undefined (both raters used one class)" if kappa is None else f"{kappa:.3f}"
    ci_text = "null" if ci is None else f"[{ci[0]:.3f}, {ci[1]:.3f}]"
    lines += [
        "# W2.6 judge_v1 vs blind human labels",
        "",
        f"Conditions: {report['conditions']}. Script `{report['script']}`.",
        "",
        f"**Cohen's kappa: {kappa_text}**, bootstrap 95% {ci_text} ({b['resamples']} resamples of the "
        f"{report['n']} answers, seed {b['seed']}, percentile; {b['undefined_resamples']} resamples undefined and "
        "left out).",
        f"Raw agreement: {ra['k']}/{ra['n']} = {ra['value']:.3f}, Wilson 95% "
        f"[{ra['ci95_wilson'][0]:.3f}, {ra['ci95_wilson'][1]:.3f}].",
        f"Human labels: {hp['k']}/{hp['n']} pass, {hp['n'] - hp['k']}/{hp['n']} fail.",
        f"Invalid judge rows: {report['invalid_judge_rows']} ({report['invalid_rule']}). Failed API calls: "
        f"{report['call_errors']} (the run stops on one and is resumed; no row is recorded from a failed call).",
        f"Plan threshold (docs/STATUS.md): kappa >= {report['plan_threshold']}; met: "
        f"{report['kappa_meets_plan_threshold']}.",
        "",
        "| human \\ judge | pass | fail | invalid |",
        "|---|---|---|---|",
    ]
    for h in ("pass", "fail"):
        row = m[f"human_{h}"]
        lines.append(f"| {h} | {row['judge_pass']} | {row['judge_fail']} | {row['judge_invalid']} |")
    lines += ["", "| Source run | n | human pass | agree |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['n']} | {v['human_pass']} | {v['agree']} |" for k, v in report["by_source_run"].items()]
    lines += ["", "Disagreements (judge reason at item level):", ""]
    lines += [
        f"- {d['id']} ({d['source_run']}): human {d['human_pass']}, judge {d['judge_pass']}. {d['judge_reason']}"
        for d in report["disagreements"]
    ] or ["- none"]
    return "\n".join(lines) + "\n"


# Command line --------------------------------------------------------------------------------------------------


def fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def latest_folder(results_dir: Path) -> Path | None:
    folders = sorted(p for p in results_dir.glob(f"*{FOLDER_SUFFIX}") if p.is_dir())
    return folders[-1] if folders else None


def is_inside(path: Path, parent: Path) -> bool:
    return path.resolve().is_relative_to(parent.resolve())


def cmd_sheet(args: argparse.Namespace) -> int:
    out = args.dir or RESULTS_DIR / f"{date.today().isoformat()}{FOLDER_SUFFIX}"
    path = out / LABELS
    if path.exists():
        return fail(f"{rel(path)} exists; the sheet is never overwritten (labels may be in it)")
    try:
        rows, provenance = build_rows()
    except (ValueError, KeyError, FileNotFoundError) as exc:
        return fail(f"stopped: {exc}")
    out.mkdir(parents=True, exist_ok=True)
    write_sheet(rows, path)
    provenance |= {
        "commit": git_commit(),
        "dirty": git_dirty_files(DIRTY_PATHS, cwd=ROOT),
        "untracked": git_untracked([Path(__file__)]),
        "written_at": now(),
        "script": SCRIPT,
        "columns": list(COLUMNS),
        "how_to_label": HOW_TO_LABEL,
    }
    (out / "sheet.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} rows")
    return 0


def _folder(args: argparse.Namespace) -> Path | None:
    return args.dir or latest_folder(RESULTS_DIR)


def _stop_reason(result: dict, model: str) -> str | None:
    """A failed API call or a reply from another model stops the run: neither says anything about the judge."""
    for a in result["attempts"]:
        if a["api_error"]:
            return f"API error: {a['api_error']}"
        if a["model"] != model:
            return f"requested {model}, returned {a['model']!r} (the judge model is not switched)"
    return None


def cmd_run(args: argparse.Namespace) -> int:
    out = _folder(args)
    if out is None or not (out / LABELS).exists():
        return fail(f"no {LABELS} found; run `python {SCRIPT} sheet` first")
    labels_path = out / LABELS
    if args.dry_run and is_inside(out, RESULTS_DIR):
        return fail("a dry run needs --dir outside results/ (copy a labelled sheet there)")
    if not args.dry_run and not is_inside(out, RESULTS_DIR):
        return fail("a real run reads only a sheet under results/ in this repository (blind order)")
    try:
        rows, provenance = build_rows()
        sheet = read_sheet(labels_path)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        return fail(f"stopped: {exc}")
    problems = label_problems(sheet, rows)
    if problems:
        return fail("; ".join(problems) + ". Label every row first (true or false).")
    git_problem, labels_commit = labels_git_state(labels_path)
    if git_problem and not args.dry_run:
        return fail(f"{git_problem}; commit the labelled sheet before the judge runs (blind order)")

    system, template = load_judge_prompt()
    code_files = [Path(__file__), ROOT / "eval" / "run_e2e.py", jsoncall.PROMPTS_DIR / f"{PROMPT_VERSION}.md"]
    dirty = git_dirty_files(DIRTY_PATHS, cwd=ROOT)
    untracked = git_untracked(code_files)
    clean = dirty == [] and untracked == []
    if not args.dry_run and not clean and not args.allow_dirty:
        return fail(
            f"uncommitted changes {dirty}, not in the commit {untracked}; commit first (R8) or pass --allow-dirty"
        )

    outputs_path, config_path = out / OUTPUTS, out / "config.json"
    done = load_jsonl(outputs_path) if outputs_path.exists() else []
    previous = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else None
    if done and not args.resume:
        return fail(f"{rel(outputs_path)} already has results; --resume judges only the missing rows")
    if args.resume:
        if previous is None:
            return fail("nothing to resume: no config.json")
        same = {
            "labels_sha256": lf_sha256(labels_path),
            "prompt_sha256": lf_sha256(jsoncall.PROMPTS_DIR / f"{PROMPT_VERSION}.md"),
            "judge_sha256": lf_sha256(Path(__file__)),
            "dry_run": args.dry_run,
        }
        changed = [k for k, v in same.items() if previous.get(k) != v]
        if changed:
            return fail(f"cannot resume: {', '.join(changed)} differ from the stopped run")
    done_keys = {(r["id"], r["source_run"]) for r in done}
    todo = [(row, s) for row, s in zip(rows, sheet, strict=True) if (s["id"], s["source_run"]) not in done_keys]
    if not todo:
        return fail("every row is judged already; run `kappa`")

    n_calls = 1 + len(todo)
    if not args.dry_run:
        print(
            f"1 smoke call + {len(todo)} rows = {n_calls} calls (up to {2 * n_calls} with retries) to {JUDGE_MODEL}; "
            "no list price in config/prices.json; actual spend on the free plan 0 USD."
        )
        if n_calls > BUDGET_WITHOUT_ASKING and not args.yes:
            if input("Continue? [y/N] ").strip().lower() != "y":
                return 1
    inner = DryRunJudgeClient() if args.dry_run else OpenAICompatibleClient(model=JUDGE_MODEL)
    client = CountingClient(inner, sleep_s=args.sleep)

    earlier = previous if args.resume else {}
    reasons = []
    if args.dry_run:
        reasons.append("dry run with the offline fake judge")
    if git_problem:
        reasons.append(git_problem)
    if not clean:
        reasons.append(f"code not clean: uncommitted {dirty}, not in the commit {untracked}")
    commit = git_commit()
    if args.resume and earlier.get("commit") != commit:
        reasons.append(f"resumed at commit {commit}, started at {earlier.get('commit')}")
    session = {"started_at": now(), "commit": commit, "argv": [SCRIPT, *args.argv], "rows": 0}
    config = {
        "commit": earlier.get("commit") or commit,
        "dirty": dirty,
        "untracked": untracked,
        "judge_sha256": lf_sha256(Path(__file__)),
        "model": {"requested": client.model, "returned": []},
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": lf_sha256(jsoncall.PROMPTS_DIR / f"{PROMPT_VERSION}.md"),
        "temperature": TEMPERATURE,
        "labels_path": rel(labels_path),
        "labels_sha256": lf_sha256(labels_path),
        "labels_commit": labels_commit,
        "sheet": provenance,
        "n": len(rows),
        "verdict_rule": "pass = every must_include met and no must_not met, computed in code from the items",
        "invalid_rule": INVALID_RULE,
        "smoke": earlier.get("smoke", []),
        "sessions": [*earlier.get("sessions", []), session],
        "started_at": earlier.get("started_at") or now(),
        "finished_at": None,
        "complete": False,
        "stopped": None,
        "n_calls": 0,
        "call_errors": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "sleep_s": args.sleep,
        "dry_run": args.dry_run,
        "not_for_reporting_reasons": [*earlier.get("not_for_reporting_reasons", []), *reasons],
        "script": SCRIPT,
    }
    base = {k: earlier.get(k) or 0 for k in ("n_calls", "call_errors", "input_tokens", "output_tokens")}
    returned_before = set((earlier.get("model") or {}).get("returned") or [])

    def write_config() -> None:
        config["n_calls"] = base["n_calls"] + len(client.calls)
        config["call_errors"] = base["call_errors"] + sum(c["error"] is not None for c in client.calls)
        config["input_tokens"] = base["input_tokens"] + sum(c["input_tokens"] for c in client.calls)
        config["output_tokens"] = base["output_tokens"] + sum(c["output_tokens"] for c in client.calls)
        config["model"]["returned"] = sorted(returned_before | {c["model"] for c in client.calls if c["model"]})
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def stop(reason: str) -> int:
        config["stopped"] = reason
        config["finished_at"] = now()
        write_config()
        return fail(f"{reason}; stopped. Finished rows are kept; `run --resume` judges the rest")

    smoke = judge_answer(
        client, system, template, SMOKE["question"], SMOKE["answer"], SMOKE["must_include"], SMOKE["must_not"]
    )
    config["smoke"] = [*config["smoke"], {"valid": smoke["valid"], "attempts": smoke["attempts"]}]
    reason = _stop_reason(smoke, client.model)
    if reason or not smoke["valid"]:
        return stop(f"smoke call: {reason or 'invalid reply twice'}")
    print(f"smoke call: model {smoke['attempts'][0]['model']}, valid reply")

    valid = sum(r["valid"] for r in done)
    invalid = len(done) - valid
    with outputs_path.open("a", encoding="utf-8") as f:
        for row, s in todo:
            result = judge_answer(
                client, system, template, row["question"], row["answer"], row["must_include"], row["must_not"]
            )
            reason = _stop_reason(result, client.model)
            if reason:
                return stop(f"row {s['id']} ({s['source_run']}): {reason}")
            f.write(json.dumps({"id": s["id"], "source_run": s["source_run"], **result}, ensure_ascii=False) + "\n")
            f.flush()
            session["rows"] += 1
            valid += result["valid"]
            invalid += not result["valid"]
            print(f"[{valid + invalid}/{len(rows)}] valid {valid}, invalid {invalid}")
    config["complete"] = True
    config["finished_at"] = now()
    write_config()
    print(f"wrote {rel(out)}; next: python {SCRIPT} kappa" + (f" --dir {args.dir}" if args.dir else ""))
    return 0


def cmd_kappa(args: argparse.Namespace) -> int:
    out = _folder(args)
    if out is None or not (out / OUTPUTS).exists() or not (out / "config.json").exists():
        return fail(f"no judge run found; run `python {SCRIPT} run` first")
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))
    labels_path = out / LABELS
    if lf_sha256(labels_path) != config["labels_sha256"]:
        return fail(f"{rel(labels_path)} changed after the judge run (sha256 differs from config.json)")
    try:
        sheet = read_sheet(labels_path)
    except ValueError as exc:
        return fail(str(exc))
    records = load_jsonl(out / OUTPUTS)
    if len(records) != len(sheet) or any(parse_label(s.get("human_pass")) is None for s in sheet):
        return fail("judge outputs and labels do not cover the same rows")
    report = kappa_report(sheet, records, config)
    (out / "kappa.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown = summary_markdown(report)
    (out / "summary.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"wrote {rel(out / 'kappa.json')}, {rel(out / 'summary.md')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("sheet", "write the labelling sheet (no model call)"),
        ("run", "judge the 20 answers (after the labels are committed)"),
        ("kappa", "agreement and Cohen's kappa"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--dir", type=Path, default=None, help=f"folder (default: the latest results/*{FOLDER_SUFFIX})")
        if name == "run":
            p.add_argument("--sleep", type=float, default=0.0, help="seconds between model calls")
            p.add_argument("--yes", action="store_true", help="skip the paid-call budget prompt")
            p.add_argument("--dry-run", action="store_true", help="offline fake judge, free; needs --dir")
            p.add_argument("--allow-dirty", action="store_true", help="code not committed (not for reporting)")
            p.add_argument("--resume", action="store_true", help="after a stopped run: judge only the missing rows")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    args = build_parser().parse_args(argv)
    args.argv = argv
    return {"sheet": cmd_sheet, "run": cmd_run, "kappa": cmd_kappa}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
