"""W3.6 claim-level faithfulness of cited answers: an LLM judge checked against two blind human raters.

    python eval/faithfulness.py sheet --run results/<date>_e2e_w3-real-ansv2_<model>   # no model call
    python eval/faithfulness.py run --sleep 13 --yes      # only after both label files are labelled and committed
    python eval/faithfulness.py kappa                     # three kappas, the decision rule, summary.json/.md
    python eval/faithfulness.py run --dry-run --dir <tmp> # offline fake judge, on a copy of labelled sheets
    python eval/faithfulness.py run --resume --sleep 13   # after a stopped run: judges only the missing claims

Order, enforced in code: sheet -> both raters label blind -> both label files committed in one commit -> run ->
kappa. `run` refuses until every `supported` cell in labels_rater1.csv (Gökçe) and labels_rater2.csv (Mert) is
true or false, both files are committed, unchanged and last touched by the same commit; it records both sha256s
and never prints a verdict. `kappa` refuses if either file changed after the run.

Blindness rule: the code cannot stop one rater from opening the other's file, so the rule is a team rule. Each
rater fills in only their own file, locally, without opening the other file or any judge output, and both files are
committed together in one commit. Neither file ever holds judge output. Edit the files as UTF-8 with comma
separators (VS Code or LibreOffice); `run` refuses a file saved with ";" or in another encoding.

Cases: from the e2e run given with --run, the cases whose classifier intent is rule_question, whose answer did not
abstain and whose output is valid.

Claim unit: one sentence of the answer text, split in code (`split_sentences`). A sentence ends at ".", "!" or "?"
(plus any [n] markers right after it) followed by a space or a newline, and at every newline; a bullet or numbered
line is its own sentence and loses its prefix (a number followed by a lowercase word, such as "15. hafta" at the
start of a line, is a Turkish ordinal and stays). A "." is not an end after an abbreviation (Dr., vs., e.g., a.m.,
Nov., Kas., ...) or when the next word starts with a lowercase letter (Turkish ordinals such as "15. gün");
decimals and dates such as 30.11.2026 have no space after the dot. A marker belongs to the sentence it stands in or
closes, so "... 30 November [1]." and "... 30 November. [1]" give the same claim with marker 1; a line holding only
markers belongs to the sentence before. Not claims: sentences equal, after normalising, to a sentence of the fixed
abstention, referral or decline replies in aic390/agent/answer.py (English or Turkish), and heading lines (no
marker, ending in ":"). Raters and the judge use the same rule for `supported` (LABEL_RULE: `how_to_label` in
sheet.json, and the prompt). The plan asks for at least 20 claims; `sheet` warns on stderr when there are fewer.

Passages, as retrieved: sources[n-1] is {doc_id, section}; its text is every hit with that doc_id and section in the
case's trace steps with step == "search", in trace order and then rank order, each chunk once, with the text looked
up by chunk_id in data/chunks.jsonl. The file's sha256 must equal the one in the run's config.json. A claim is judged
against the passages its markers cite; a claim without a marker is judged against every source of its answer and has
has_marker = false.

Sample: if there are at most 40 eligible claims, all of them go on the sheet; otherwise
random.Random(0).sample(the eligible claims in file order, 40), shown in file order.

Judge: qwen/qwen3.8-27b, T = 0, prompts/faithfulness_v1.md, one call per claim with {"supported": true|false}. A
reply that is invalid twice gives supported = null; in each kappa it counts as a disagreement with that rater. A
failed API call or a reply from another model stops the run; `--resume` finishes it.

Decision rule (docs/STATUS.md, W3.6 plan row): if the judge's kappa is >= 0.6 against both raters,
unsupported_claims = claims the judge marked unsupported / claims with a valid judge reply, with the number of
invalid replies and the worst case (invalid counted as unsupported, over all claims) beside it. Otherwise
unsupported_claims = claims that either rater marked unsupported / all sheet claims, with each rater's rate and the
rate on the claims both raters agree on beside it, and a reason.
"""

import argparse
import csv
import json
import random
import re
import sys
from datetime import date
from pathlib import Path

from pydantic import BaseModel, StrictBool

from aic390 import jsoncall
from aic390.agent.answer import ABSTENTIONS, DECLINE, MARKER, OTHER_STUDENT
from aic390.llm import ChatClient, FakeClient, LLMResponse, OpenAICompatibleClient
from aic390.stats import cohen_kappa, kappa_bootstrap_ci

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
from judge import (  # noqa: E402
    _squash,
    _stop_reason,
    fail,
    is_inside,
    labels_git_state,
    latest_folder,
    load_jsonl,
    load_judge_prompt,
    now,
    parse_label,
    proportion,
    read_sheet,
)
from run_e2e import (  # noqa: E402
    BUDGET_WITHOUT_ASKING,
    CountingClient,
    git_commit,
    git_dirty_files,
    git_untracked,
    lf_sha256,
    rel,
)

SCRIPT = "eval/faithfulness.py"
RESULTS_DIR = ROOT / "results"  # where the faithfulness folder goes
REPO = ROOT  # the git repository the label files must be committed in
CHUNKS = ROOT / "data" / "chunks.jsonl"
FOLDER_SUFFIX = "_faithfulness-v1"
RATERS = {"rater1": "Serap Gökçe Yıldız", "rater2": "Mert Bozma"}
LABEL_FILES = {"rater1": "labels_rater1.csv", "rater2": "labels_rater2.csv"}
OUTPUTS = "judge_outputs.jsonl"
COLUMNS = ("claim_id", "case_id", "question", "claim", "markers", "has_marker", "passages", "supported", "note")
JUDGE_MODEL = "qwen/qwen3.8-27b"  # D-006: a different family from the main model
PROMPT_VERSION = "faithfulness_v1"
TEMPERATURE = 0.0
ELIGIBLE_INTENT = "rule_question"
SAMPLE_MAX = 40
SAMPLE_SEED = 0
SAMPLE_RULE = (
    f"all eligible claims if there are at most {SAMPLE_MAX}; otherwise random.Random({SAMPLE_SEED}).sample(the "
    f"eligible claims in file order, {SAMPLE_MAX}), shown in file order"
)
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0
KAPPA_PLAN_THRESHOLD = 0.6  # docs/STATUS.md, Experiments plan row for W3.6
DIRTY_PATHS = ("src", "prompts", "eval", "scripts")
LABEL_RULE = (
    "supported = true when the passages state every fact in the claim; a paraphrase, another language or another "
    "number or date format counts; any fact the passages do not state makes it false; use only the passages, not "
    "what you know; the question is context, not evidence (the same rule as prompts/faithfulness_v1.md)"
)
HOW_TO_LABEL = f"{LABEL_RULE}; write true or false; edit as UTF-8 with comma separators (VS Code or LibreOffice)"
PLAN_MINIMUM_CLAIMS = 20  # docs/STATUS.md, W3.6 plan row: "at least 20 claims"
INVALID_RULE = (
    "an invalid judge reply (supported null) counts as a disagreement in each kappa: it takes the opposite of that "
    "rater's label, which also shifts the judge's class rates used in kappa's expected agreement"
)
MARKER_SEPARATOR = ";"

# The invented example of prompts/faithfulness_v1.md, sent once before the claims to check that the provider
# serves the judge model.
SMOKE = {
    "question": "BIO-204 final sınavına giremezsem ne yapmalıyım?",
    "claim": "Final sınavına giremeyen öğrenci doktor raporu sunmalı ve mazeret sınavı 15 Ocak'ta yapılır.",
    "passages": (
        "[1] bio204-syllabus · Make-up exams\n"
        "A student who misses the final exam must submit a medical report or another excuse document to the "
        "department\noffice within three working days."
    ),
}


# Claims --------------------------------------------------------------------------------------------------------

BULLET = re.compile(r"^\s*(?:[-*•+]|\d{1,3}[.)])\s+(?=(\S?))")
SENTENCE_END = re.compile(r"[.!?]((?:\s*\[\d+\])*)(?=\s|$)")
ABBREVIATIONS = {
    "dr.", "prof.", "doç.", "doc.", "assoc.", "asst.", "mr.", "mrs.", "ms.", "st.", "no.", "nr.", "art.", "sec.",
    "vs.", "e.g.", "i.e.", "etc.", "cf.", "approx.", "örn.", "vb.", "vd.", "bkz.", "yy.", "sn.", "md.", "s.",
    "a.m.", "p.m.", "jan.", "feb.", "mar.", "apr.", "jun.", "jul.", "aug.", "sep.", "sept.", "oct.", "nov.", "dec.",
    "oca.", "şub.", "nis.", "haz.", "tem.", "ağu.", "eyl.", "eki.", "kas.", "ara.",
}  # fmt: skip
OPENERS = "(\"'«“‘["


def _ends_sentence(line: str, match: re.Match) -> bool:
    if line[match.start()] != ".":
        return True
    word = line[: match.start() + 1].split()[-1].lstrip(OPENERS).casefold()
    if word in ABBREVIATIONS:
        return False
    following = line[match.end() :].lstrip()
    return not following[:1].islower()


def _strip_bullet(line: str) -> str:
    """A bullet or list number is removed; "15. hafta" at the start of a line is a Turkish ordinal, not a list
    number, so a number followed by a lowercase word stays."""
    match = BULLET.match(line)
    if match is None or (match.group(0).strip()[0].isdigit() and match.group(1).islower()):
        return line
    return line[match.end() :]


def _clean(text: str) -> str:
    return re.sub(r" +([.,;:!?])", r"\1", _squash(MARKER.sub("", text))).strip()


def split_sentences(text: str) -> list[dict]:
    """Every sentence of `text` as {text, markers}: the text without its [n] markers, the marker numbers in order of
    first use. Segments with no letter or digit only carry their markers to the sentence before."""
    sentences: list[dict] = []

    def add(segment: str) -> None:
        markers = [int(m) for m in MARKER.findall(segment)]
        cleaned = _clean(segment)
        if not any(ch.isalnum() for ch in cleaned):
            if sentences and markers:
                sentences[-1]["markers"] += [m for m in markers if m not in sentences[-1]["markers"]]
            return
        sentences.append({"text": cleaned, "markers": list(dict.fromkeys(markers))})

    for raw in (text or "").splitlines():
        line = _strip_bullet(raw)
        start = 0
        for match in SENTENCE_END.finditer(line):
            if _ends_sentence(line, match):
                add(line[start : match.end()])
                start = match.end()
        add(line[start:])
    return sentences


def normalise(text: str) -> str:
    return _clean(text).casefold().rstrip(" .!?")


def _fixed_sentences() -> set[str]:
    replies = [*(r for kind in ABSTENTIONS.values() for r in kind.values()), *DECLINE.values(), *OTHER_STUDENT.values()]
    found = {normalise(r) for r in replies}
    found |= {normalise(s["text"]) for r in replies for s in split_sentences(r)}
    return found


FIXED_SENTENCES = _fixed_sentences()


def split_claims(text: str) -> list[dict]:
    """The claims of an answer: its sentences without the fixed abstention, referral and decline sentences, and
    without heading lines (no marker, ending in ":"), which state no fact."""
    return [
        s
        for s in split_sentences(text)
        if normalise(s["text"]) not in FIXED_SENTENCES and not (not s["markers"] and s["text"].endswith(":"))
    ]


# Passages ------------------------------------------------------------------------------------------------------


def load_chunks(path: Path) -> dict[str, str]:
    return {row["chunk_id"]: row["text"] for row in load_jsonl(path)}


def retrieved_chunks(trace: list[dict]) -> dict[tuple[str, str], list[str]]:
    """(doc_id, section) -> chunk_ids, from every search step in trace order and then rank order, each chunk once."""
    found: dict[tuple[str, str], list[str]] = {}
    seen = set()
    for step in trace or []:
        if step.get("step") != "search":
            continue
        for hit in sorted(step.get("hits") or [], key=lambda h: h["rank"]):
            if hit["chunk_id"] in seen:
                continue
            seen.add(hit["chunk_id"])
            found.setdefault((hit["doc_id"], hit["section"]), []).append(hit["chunk_id"])
    return found


def source_passages(case_id: str, output: dict, chunks: dict[str, str]) -> list[str]:
    """One passage per source, in the order of `sources`: "[n] doc_id · section" and the text as retrieved."""
    retrieved = retrieved_chunks(output.get("trace"))
    passages = []
    for n, source in enumerate(output["sources"], 1):
        ids = retrieved.get((source["doc_id"], source["section"]))
        if not ids:
            raise ValueError(f"{case_id}: source [{n}] {source['doc_id']} · {source['section']} is not in the trace")
        missing = [c for c in ids if c not in chunks]
        if missing:
            raise ValueError(f"{case_id}: chunk_id not in {rel(CHUNKS)}: {', '.join(missing)}")
        text = "\n".join(chunks[c] for c in ids)
        passages.append(f"[{n}] {source['doc_id']} · {source['section']}\n{text}")
    return passages


# Sheet ---------------------------------------------------------------------------------------------------------


def eligible(record: dict) -> bool:
    output = record.get("output")
    return (
        record.get("error") is None
        and output is not None
        and (output.get("classifier") or {}).get("intent") == ELIGIBLE_INTENT
        and output.get("abstain") is False
        and output.get("valid") is True
    )


def _repo_path(text: str) -> Path:
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


def sample_indices(n: int) -> list[int]:
    if n <= SAMPLE_MAX:
        return list(range(n))
    return sorted(random.Random(SAMPLE_SEED).sample(range(n), SAMPLE_MAX))


def build_rows(run_dir: Path) -> tuple[list[dict], dict]:
    """The sheet rows (without labels) and the provenance written to sheet.json. Raises ValueError when the run
    cannot give passages as retrieved."""
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    answer_prompt = (config.get("prompts") or {}).get("answer", "answer_v1")
    if answer_prompt == "answer_v1":
        raise ValueError(
            f"{rel(run_dir)} used answer_v1, whose markers do not point at `sources`; W3.6 needs answer_v2"
        )
    expected_sha = (config.get("search") or {}).get("chunks_sha256")
    if expected_sha is None:
        raise ValueError(f"{rel(run_dir)} has no search.chunks_sha256 in config.json (stub search?)")
    actual_sha = lf_sha256(CHUNKS)
    if actual_sha != expected_sha:
        raise ValueError(f"{rel(CHUNKS)} sha256 {actual_sha} differs from {expected_sha} in the run's config.json")
    chunks = load_chunks(CHUNKS)
    cases_path = _repo_path(config["cases_path"])
    if lf_sha256(cases_path) != config["cases_sha256"]:
        raise ValueError(f"{rel(cases_path)} differs from the test set the run used (sha256)")
    questions = {c["id"]: c["text"] for c in load_jsonl(cases_path)}
    outputs_path = run_dir / "outputs.jsonl"

    claims, case_ids = [], []
    for record in load_jsonl(outputs_path):
        if not eligible(record):
            continue
        case_id, output = record["id"], record["output"]
        case_ids.append(case_id)
        passages = source_passages(case_id, output, chunks)
        for k, claim in enumerate(split_claims(output["answer_text"]), 1):
            bad = [m for m in claim["markers"] if not 1 <= m <= len(passages)]
            if bad:
                raise ValueError(f"{case_id}#{k}: marker {bad} names no source")
            cited = [passages[m - 1] for m in claim["markers"]] or passages
            claims.append(
                {
                    "claim_id": f"{case_id}#{k}",
                    "case_id": case_id,
                    "question": questions[case_id],
                    "claim": claim["text"],
                    "markers": claim["markers"],
                    "has_marker": bool(claim["markers"]),
                    "passages": "\n\n".join(cited),
                }
            )
    rows = [claims[i] for i in sample_indices(len(claims))]
    provenance = {
        "run": rel(run_dir),
        "run_commit": config.get("commit"),
        "run_prompts": config.get("prompts"),
        "run_model": (config.get("model") or {}).get("requested"),
        "outputs_sha256": lf_sha256(outputs_path),
        "cases_path": rel(cases_path),
        "cases_sha256": config["cases_sha256"],
        "chunks_path": rel(CHUNKS),
        "chunks_sha256": actual_sha,
        "eligibility": f"classifier intent {ELIGIBLE_INTENT}, abstain false, valid true, no error",
        "eligible_case_ids": case_ids,
        "eligible_claims": len(claims),
        "sample_rule": SAMPLE_RULE,
        "sampled": len(rows) < len(claims),
        "cases": len({r["case_id"] for r in rows}),
        "n": len(rows),
        "claims_without_marker": sum(not r["has_marker"] for r in rows),
        "plan_minimum_claims": PLAN_MINIMUM_CLAIMS,
        "meets_plan_minimum": len(rows) >= PLAN_MINIMUM_CLAIMS,
        "claim_ids": [r["claim_id"] for r in rows],
    }
    return rows, provenance


def write_sheet(rows: list[dict], path: Path) -> None:
    # utf-8-sig so a spreadsheet program opens the Turkish text correctly
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "markers": MARKER_SEPARATOR.join(str(m) for m in row["markers"]),
                    "has_marker": "true" if row["has_marker"] else "false",
                    "supported": "",
                    "note": "",
                }
            )


# Labels --------------------------------------------------------------------------------------------------------


def label_problems(name: str, sheet: list[dict], rows: list[dict]) -> list[str]:
    """Why a label file cannot be used: rows that differ from the rebuilt sheet, or a `supported` that is not true
    or false. Says which rows, never which value."""
    if [s.get("claim_id") for s in sheet] != [r["claim_id"] for r in rows]:
        return [f"{name}: rows (claim_id) differ from the sheet that `sheet` builds"]
    problems = []
    changed = [
        r["claim_id"]
        for r, s in zip(rows, sheet, strict=True)
        if _squash(s.get("claim")) != _squash(r["claim"]) or _squash(s.get("passages")) != _squash(r["passages"])
    ]
    if changed:
        problems.append(f"{name}: claim or passages changed in rows: " + ", ".join(changed))
    empty = [f"{i} ({s['claim_id']})" for i, s in enumerate(sheet, 1) if parse_label(s.get("supported")) is None]
    if empty:
        problems.append(f"{name}: supported is not true or false in rows: " + ", ".join(empty))
    return problems


def read_labels(path: Path) -> list[dict]:
    return read_sheet(path, COLUMNS, HOW_TO_LABEL)


# Judging -------------------------------------------------------------------------------------------------------


class FaithfulnessReply(BaseModel):
    supported: StrictBool


def user_message(template: str, question: str, claim: str, passages: str) -> str:
    # one pass, so a "{claim}" inside the question is never filled in
    values = {"question": question, "claim": claim, "passages": passages}
    return re.sub(r"\{(question|claim|passages)\}", lambda m: values[m.group(1)], template)


def parse_reply(text: str) -> bool:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)  # reasoning models may prefix their thinking
    return jsoncall.parse_json(text, FaithfulnessReply).supported


def judge_claim(client: ChatClient, system: str, template: str, question: str, claim: str, passages: str) -> dict:
    """One claim: the first call plus one retry on an invalid reply. A failed API call is not retried here (the
    client already retries rate limits)."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message(template, question, claim, passages)},
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
            supported = parse_reply(resp.text)
        except ValueError as exc:
            record["invalid_reason"] = str(exc)
            messages += [
                {"role": "assistant", "content": resp.text},
                {"role": "user", "content": f"Your reply was not valid ({exc}). Reply with the JSON object only."},
            ]
            continue
        return {"valid": True, "supported": supported, "attempts": attempts}
    return {"valid": False, "supported": None, "attempts": attempts}


class DryRunJudgeClient(FakeClient):
    """Offline judge for --dry-run: says every claim is supported. Says nothing about real answers."""

    def __init__(self, model: str = "fake-judge"):
        super().__init__(model)

    def chat(self, messages: list[dict], temperature: float) -> LLMResponse:
        prompt = " ".join(m["content"] for m in messages)
        return LLMResponse(
            text='{"supported": true}',
            model=self.model,
            input_tokens=len(prompt) // 4,
            output_tokens=6,
            latency_s=0.0,
            model_requested=self.model,
        )


# Kappa ---------------------------------------------------------------------------------------------------------


def share(k: int, n: int) -> dict | None:
    return proportion(k, n) if n else None


def _class(label: bool | None) -> str:
    return {True: "supported", False: "unsupported", None: "invalid"}[label]


def pair_report(a: list[bool], b_raw: list[bool | None], a_name: str, b_name: str) -> dict:
    """Kappa of rater `a` against `b`; a null in `b` (invalid judge reply) takes the opposite of `a`."""
    b = [(not x) if y is None else y for x, y in zip(a, b_raw, strict=True)]
    n = len(a)
    kappa = cohen_kappa(a, b)
    lo, hi, undefined = kappa_bootstrap_ci(a, b, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
    columns = (True, False, None) if b_name == "judge" else (True, False)
    matrix = {
        f"{a_name}_{_class(x)}": {
            f"{b_name}_{_class(y)}": sum(1 for p, q in zip(a, b_raw, strict=True) if p is x and q is y) for y in columns
        }
        for x in (True, False)
    }
    return {
        "n": n,
        "cohen_kappa": None if kappa is None else round(kappa, 4),
        "meets_plan_threshold": kappa is not None and kappa >= KAPPA_PLAN_THRESHOLD,  # unrounded
        "kappa_ci95_bootstrap": None if lo is None else [round(lo, 4), round(hi, 4)],
        "bootstrap_undefined_resamples": undefined,
        "raw_agreement": proportion(sum(x == y for x, y in zip(a, b, strict=True)), n),
        "confusion_matrix": matrix,
    }


def unsupported_claims(r1: list[bool], r2: list[bool], judge: list[bool | None], pairs: dict) -> dict:
    k1, k2 = pairs["judge_vs_rater1"]["cohen_kappa"], pairs["judge_vs_rater2"]["cohen_kappa"]
    n = len(r1)
    if pairs["judge_vs_rater1"]["meets_plan_threshold"] and pairs["judge_vs_rater2"]["meets_plan_threshold"]:
        valid = [j for j in judge if j is not None]
        unsupported = sum(not j for j in valid)
        invalid = n - len(valid)
        return {
            "source": "judge",
            "rule": "claims the judge marked unsupported / claims with a valid judge reply",
            **(share(unsupported, len(valid)) or {"k": 0, "n": 0, "value": None, "ci95_wilson": None}),
            "judge_invalid": invalid,
            "worst_case": {
                "rule": "judge unsupported + invalid replies / all claims",
                **proportion(unsupported + invalid, n),
            },
        }
    agreed = [x for x, y in zip(r1, r2, strict=True) if x == y]
    text = {None: "undefined"}
    return {
        "source": "human",
        "rule": "claims that either rater marked unsupported / all sheet claims",
        **proportion(sum((not x) or (not y) for x, y in zip(r1, r2, strict=True)), n),
        "reason": (
            f"judge kappa {text.get(k1, k1)} against rater 1 and {text.get(k2, k2)} against rater 2; the plan needs "
            f">= {KAPPA_PLAN_THRESHOLD} against both, so the human labels are used"
        ),
        "rater1": proportion(sum(not x for x in r1), n),
        "rater2": proportion(sum(not y for y in r2), n),
        "agreed_only": {
            "rule": "claims both raters marked unsupported / claims both raters labelled the same",
            **(share(sum(not x for x in agreed), len(agreed)) or {"k": 0, "n": 0, "value": None, "ci95_wilson": None}),
        },
    }


def kappa_report(labels1: list[dict], labels2: list[dict], records: list[dict], config: dict) -> dict:
    by_claim = {r["claim_id"]: r for r in records}
    r1 = [parse_label(s["supported"]) for s in labels1]
    r2 = [parse_label(s["supported"]) for s in labels2]
    judge = [by_claim[s["claim_id"]]["supported"] for s in labels1]
    pairs = {
        "judge_vs_rater1": pair_report(r1, judge, "rater1", "judge"),
        "judge_vs_rater2": pair_report(r2, judge, "rater2", "judge"),
        "rater1_vs_rater2": pair_report(r1, r2, "rater1", "rater2"),
    }
    disagreements = []
    for s, x, y, j in zip(labels1, r1, r2, judge, strict=True):
        checks = (("judge_vs_rater1", j != x), ("judge_vs_rater2", j != y), ("rater1_vs_rater2", x != y))
        which = [name for name, bad in checks if bad]
        if which:
            disagreements.append(
                {
                    "claim_id": s["claim_id"],
                    "case_id": s["case_id"],
                    "claim": s["claim"],
                    "rater1": x,
                    "rater2": y,
                    "judge": j,
                    "pairs": which,
                }
            )
    problems = list(config.get("not_for_reporting_reasons") or [])
    if not config.get("complete"):
        problems.append("judge run did not finish")
    if config["model"]["returned"] != [config["model"]["requested"]]:
        problems.append(f"models returned {config['model']['returned']}, requested {config['model']['requested']}")
    return {
        "for_reporting": not problems,
        "not_for_reporting_reasons": problems,
        "n": len(labels1),
        "claims_without_marker": sum(parse_label(s["has_marker"]) is False for s in labels1),
        "sample": {
            "rule": SAMPLE_RULE,
            "eligible_claims": (config.get("sheet") or {}).get("eligible_claims"),
            "sampled": (config.get("sheet") or {}).get("sampled"),
        },
        "pairs": pairs,
        "bootstrap": {
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "unit": "claim (row), with replacement",
            "method": "percentile",
        },
        "invalid_judge_rows": sum(j is None for j in judge),
        "call_errors": config.get("call_errors"),
        "invalid_rule": INVALID_RULE,
        "plan_threshold": KAPPA_PLAN_THRESHOLD,
        "judge_meets_threshold_against_both": pairs["judge_vs_rater1"]["meets_plan_threshold"]
        and pairs["judge_vs_rater2"]["meets_plan_threshold"],
        "unsupported_claims": unsupported_claims(r1, r2, judge, pairs),
        "disagreements": disagreements,
        "conditions": conditions_text(config),
        "script": SCRIPT,
    }


def conditions_text(config: dict) -> str:
    returned = ", ".join(config["model"]["returned"]) or "none"
    labels = "; ".join(f"{k} sha256 {v['sha256']}" for k, v in config["labels"].items())
    return (
        f"commit {config['commit']}, judge model {config['model']['requested']} (returned: {returned}), "
        f"prompt {config['prompt_version']}, T={config['temperature']}, answers from {config['sheet']['run']}, "
        f"labels {labels} (labels commit {config['labels_commit']})"
    )


def _kappa_text(p: dict) -> tuple[str, str]:
    kappa, ci = p["cohen_kappa"], p["kappa_ci95_bootstrap"]
    k = "undefined (one class only)" if kappa is None else f"{kappa:.3f}"
    c = "null" if ci is None else f"[{ci[0]:.3f}, {ci[1]:.3f}]"
    return k, c


def _share_text(p: dict | None) -> str:
    if not p or p.get("value") is None:
        return "n = 0"
    lo, hi = p["ci95_wilson"]
    return f"{p['k']}/{p['n']} = {p['value']:.3f}, Wilson 95% [{lo:.3f}, {hi:.3f}]"


def summary_markdown(report: dict) -> str:
    lines = []
    if not report["for_reporting"]:
        lines += ["**NOT FOR REPORTING**: " + "; ".join(report["not_for_reporting_reasons"]), ""]
    b = report["bootstrap"]
    lines += [
        "# W3.6 faithfulness_v1: judge vs two blind raters",
        "",
        f"Conditions: {report['conditions']}. Script `{report['script']}`.",
        "",
        f"Claims: {report['n']} ({report['claims_without_marker']} without a marker, judged against every source of "
        f"their answer). Sample: {report['sample']['rule']}; eligible claims {report['sample']['eligible_claims']}.",
        f"Bootstrap: {b['resamples']} resamples of the claims, seed {b['seed']}, {b['method']}.",
        f"Invalid judge replies: {report['invalid_judge_rows']} ({report['invalid_rule']}). Failed API calls: "
        f"{report['call_errors']} (the run stops on one and is resumed; no row is recorded from a failed call).",
        "",
        "| Pair | Cohen's kappa | bootstrap 95% | raw agreement |",
        "|---|---|---|---|",
    ]
    for name, p in report["pairs"].items():
        k, c = _kappa_text(p)
        lines.append(f"| {name} | {k} | {c} | {_share_text(p['raw_agreement'])} |")
    for name, p in report["pairs"].items():
        matrix = p["confusion_matrix"]
        cols = list(next(iter(matrix.values())))
        lines += ["", f"{name}:", "", "| | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
        lines += [f"| {row} | " + " | ".join(str(v[c]) for c in cols) + " |" for row, v in matrix.items()]
    u = report["unsupported_claims"]
    lines += [
        "",
        f"Plan threshold (docs/STATUS.md): judge kappa >= {report['plan_threshold']} against both raters; met: "
        f"{report['judge_meets_threshold_against_both']}.",
        "",
        f"**unsupported_claims ({u['source']})**: {_share_text(u)}. Rule: {u['rule']}.",
    ]
    if u["source"] == "judge":
        lines.append(
            f"Invalid judge replies left out: {u['judge_invalid']}. Worst case ({u['worst_case']['rule']}): "
            f"{_share_text(u['worst_case'])}."
        )
    else:
        lines += [
            f"Reason: {u['reason']}.",
            f"Rater 1: {_share_text(u['rater1'])}. Rater 2: {_share_text(u['rater2'])}. "
            f"Agreed only ({u['agreed_only']['rule']}): {_share_text(u['agreed_only'])}.",
        ]
    lines += ["", "Disagreements:", ""]
    lines += [
        f"- {d['claim_id']} ({d['case_id']}): rater1 {d['rater1']}, rater2 {d['rater2']}, judge {d['judge']} "
        f"[{', '.join(d['pairs'])}]. Claim: {d['claim']}"
        for d in report["disagreements"]
    ] or ["- none"]
    return "\n".join(lines) + "\n"


# Command line --------------------------------------------------------------------------------------------------


def _folder(args: argparse.Namespace) -> Path | None:
    return args.dir or latest_folder(RESULTS_DIR, FOLDER_SUFFIX)


def cmd_sheet(args: argparse.Namespace) -> int:
    out = args.dir or RESULTS_DIR / f"{date.today().isoformat()}{FOLDER_SUFFIX}"
    existing = [p for p in (out / "sheet.json", *(out / f for f in LABEL_FILES.values())) if p.exists()]
    if existing:
        names = ", ".join(rel(p) for p in existing)
        return fail(f"{names} exists; the sheet is never overwritten (labels may be in it)")
    try:
        rows, provenance = build_rows(args.run)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        return fail(f"stopped: {exc}")
    if not rows:
        return fail(f"no eligible claims in {rel(args.run)}; nothing to label")
    out.mkdir(parents=True, exist_ok=True)
    for name in LABEL_FILES.values():
        write_sheet(rows, out / name)
    provenance |= {
        "commit": git_commit(),
        "dirty": git_dirty_files(DIRTY_PATHS, cwd=ROOT),
        "untracked": git_untracked([Path(__file__)]),
        "written_at": now(),
        "script": SCRIPT,
        "label_files": {k: {"file": v, "rater": RATERS[k]} for k, v in LABEL_FILES.items()},
        "columns": list(COLUMNS),
        "how_to_label": HOW_TO_LABEL,
    }
    (out / "sheet.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"cases {provenance['cases']}, claims {provenance['n']} (of {provenance['eligible_claims']} eligible), "
        f"claims without a marker {provenance['claims_without_marker']}"
    )
    if not provenance["meets_plan_minimum"]:
        print(f"warning: fewer than the plan's {PLAN_MINIMUM_CLAIMS} claims", file=sys.stderr)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    out = _folder(args)
    if out is None or not (out / "sheet.json").exists():
        return fail(f"no sheet.json found; run `python {SCRIPT} sheet --run <e2e folder>` first")
    if args.dry_run and is_inside(out, RESULTS_DIR):
        return fail("a dry run needs --dir outside results/ (copy the labelled sheets there)")
    if not args.dry_run and not is_inside(out, RESULTS_DIR):
        return fail("a real run reads only label files under results/ in this repository (blind order)")
    sheet_meta = json.loads((out / "sheet.json").read_text(encoding="utf-8"))
    run_dir = _repo_path(sheet_meta["run"])
    paths = {k: out / v for k, v in LABEL_FILES.items()}
    try:
        if lf_sha256(run_dir / "outputs.jsonl") != sheet_meta["outputs_sha256"]:
            raise ValueError(f"{sheet_meta['run']}/outputs.jsonl changed after the sheet was written")
        rows, provenance = build_rows(run_dir)
        labels = {k: read_labels(p) for k, p in paths.items()}
    except (ValueError, KeyError, FileNotFoundError) as exc:
        return fail(f"stopped: {exc}")
    problems = [p for k in LABEL_FILES for p in label_problems(LABEL_FILES[k], labels[k], rows)]
    if problems:
        return fail("; ".join(problems) + ". Both raters label every row first (true or false).")
    git = {k: labels_git_state(p, REPO) for k, p in paths.items()}
    git_problems = [problem for problem, _ in git.values() if problem]
    commits = {commit for _, commit in git.values()}
    if not git_problems and (len(commits) != 1 or None in commits):
        git_problems.append(f"the two label files were last committed in different commits {sorted(commits)}")
    if git_problems and not args.dry_run:
        return fail("; ".join(git_problems) + "; commit both labelled files in one commit before the judge runs")
    labels_commit = git["rater1"][1] if not git_problems else None
    if not args.dry_run and not is_inside(run_dir, RESULTS_DIR):
        return fail(f"the answers ({sheet_meta['run']}) are not under results/; a real run judges a results run")

    system, template = load_judge_prompt(PROMPT_VERSION)
    prompt_path = jsoncall.PROMPTS_DIR / f"{PROMPT_VERSION}.md"
    code_files = [Path(__file__), ROOT / "eval" / "judge.py", ROOT / "eval" / "run_e2e.py", prompt_path]
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
        return fail(f"{rel(outputs_path)} already has results; --resume judges only the missing claims")
    label_shas = {k: lf_sha256(p) for k, p in paths.items()}
    if previous is not None and not args.resume:
        earlier_shas = {k: v.get("sha256") for k, v in (previous.get("labels") or {}).items()}
        if previous.get("complete") or earlier_shas != label_shas:
            return fail(
                f"{rel(config_path)} records an earlier run (complete, or other label sha256s); it is never replaced. "
                "Use --resume, or write a new sheet in a new folder"
            )
    if args.resume:
        if previous is None:
            return fail("nothing to resume: no config.json")
        same = {
            "labels": label_shas,
            "prompt_sha256": lf_sha256(prompt_path),
            "script_sha256": lf_sha256(Path(__file__)),
            "dry_run": args.dry_run,
        }
        before = {**previous, "labels": {k: v["sha256"] for k, v in (previous.get("labels") or {}).items()}}
        changed = [k for k, v in same.items() if before.get(k) != v]
        if changed:
            return fail(f"cannot resume: {', '.join(changed)} differ from the stopped run")
    done_ids = {r["claim_id"] for r in done}
    todo = [row for row in rows if row["claim_id"] not in done_ids]
    if not todo:
        return fail("every claim is judged already; run `kappa`")

    n_calls = 1 + len(todo)
    if not args.dry_run:
        print(
            f"1 smoke call + {len(todo)} claims = {n_calls} calls (up to {2 * n_calls} with retries) to "
            f"{JUDGE_MODEL}; no list price in config/prices.json; actual spend on the free plan 0 USD."
        )
        if 2 * n_calls > BUDGET_WITHOUT_ASKING and not args.yes:  # with retries
            if input("Continue? [y/N] ").strip().lower() != "y":
                return 1
    inner = DryRunJudgeClient() if args.dry_run else OpenAICompatibleClient(model=JUDGE_MODEL)
    client = CountingClient(inner, sleep_s=args.sleep)

    earlier = previous if args.resume else {}
    reasons = []
    if args.dry_run:
        reasons.append("dry run with the offline fake judge")
    reasons += git_problems
    if not clean:
        reasons.append(f"code not clean: uncommitted {dirty}, not in the commit {untracked}")
    commit = git_commit()
    if args.resume and earlier.get("commit") != commit:
        reasons.append(f"resumed at commit {commit}, started at {earlier.get('commit')}")
    session = {"started_at": now(), "commit": commit, "argv": [SCRIPT, *args.argv], "claims": 0}
    config = {
        "commit": earlier.get("commit") or commit,
        "dirty": dirty,
        "untracked": untracked,
        "script_sha256": lf_sha256(Path(__file__)),
        "model": {"requested": client.model, "returned": []},
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": lf_sha256(prompt_path),
        "temperature": TEMPERATURE,
        "labels": {
            k: {"path": rel(p), "rater": RATERS[k], "sha256": label_shas[k], "commit": git[k][1]}
            for k, p in paths.items()
        },
        "labels_commit": labels_commit,
        "sheet": provenance,
        "sample_rule": SAMPLE_RULE,
        "n": len(rows),
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
        return fail(f"{reason}; stopped. Finished claims are kept; `run --resume` judges the rest")

    smoke = judge_claim(client, system, template, SMOKE["question"], SMOKE["claim"], SMOKE["passages"])
    config["smoke"] = [*config["smoke"], {"valid": smoke["valid"], "attempts": smoke["attempts"]}]
    reason = _stop_reason(smoke, client.model)
    if reason or not smoke["valid"]:
        return stop(f"smoke call: {reason or 'invalid reply twice'}")
    print(f"smoke call: model {smoke['attempts'][0]['model']}, valid reply")

    valid = sum(r["valid"] for r in done)
    invalid = len(done) - valid
    with outputs_path.open("a", encoding="utf-8") as f:
        for row in todo:
            result = judge_claim(client, system, template, row["question"], row["claim"], row["passages"])
            reason = _stop_reason(result, client.model)
            if reason:
                return stop(f"claim {row['claim_id']}: {reason}")
            f.write(json.dumps({"claim_id": row["claim_id"], "case_id": row["case_id"], **result}, ensure_ascii=False))
            f.write("\n")
            f.flush()
            session["claims"] += 1
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
    paths = {k: out / v for k, v in LABEL_FILES.items()}
    changed = [rel(p) for k, p in paths.items() if lf_sha256(p) != config["labels"][k]["sha256"]]
    if changed:
        return fail(f"{', '.join(changed)} changed after the judge run (sha256 differs from config.json)")
    try:
        labels = {k: read_labels(p) for k, p in paths.items()}
    except ValueError as exc:
        return fail(str(exc))
    records = load_jsonl(out / OUTPUTS)
    ids = [s["claim_id"] for s in labels["rater1"]]
    if [s["claim_id"] for s in labels["rater2"]] != ids:
        return fail("the two label files do not list the same claims")
    if any(parse_label(s.get("supported")) is None for rows in labels.values() for s in rows):
        return fail("a label file has a row whose supported is not true or false")
    if sorted(r["claim_id"] for r in records) != sorted(ids):
        return fail("judge outputs and labels do not cover the same claims")
    report = kappa_report(labels["rater1"], labels["rater2"], records, config)
    (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown = summary_markdown(report)
    (out / "summary.md").write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"wrote {rel(out / 'summary.json')}, {rel(out / 'summary.md')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("sheet", "write sheet.json and the two label files (no model call)"),
        ("run", "judge every claim (after both label files are committed)"),
        ("kappa", "three Cohen's kappas, the decision rule, summary.json and summary.md"),
    ):
        p = sub.add_parser(name, help=help_text)
        if name == "sheet":
            p.add_argument("--run", type=Path, required=True, help="the e2e results folder whose answers are judged")
            p.add_argument("--dir", type=Path, default=None, help=f"folder (default: results/<today>{FOLDER_SUFFIX})")
        else:
            latest = f"folder (default: the latest results/*{FOLDER_SUFFIX})"
            p.add_argument("--dir", type=Path, default=None, help=latest)
        if name == "run":
            p.add_argument("--sleep", type=float, default=0.0, help="seconds between model calls")
            p.add_argument("--yes", action="store_true", help="skip the paid-call budget prompt")
            p.add_argument("--dry-run", action="store_true", help="offline fake judge, free; needs --dir")
            p.add_argument("--allow-dirty", action="store_true", help="code not committed (not for reporting)")
            p.add_argument("--resume", action="store_true", help="after a stopped run: judge only the missing claims")
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
