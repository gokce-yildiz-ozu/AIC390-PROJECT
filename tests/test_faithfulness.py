"""Offline tests for the W3.6 faithfulness judge: a fixture e2e folder, a fixture chunks file, fake judge clients and
a temporary git repository; no model is called and nothing is written under results/."""

import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from aic390.agent.answer import ABSTENTIONS, DECLINE, NOT_FOUND, OTHER_STUDENT
from aic390.llm import FakeClient, LLMResponse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import faithfulness as fa  # noqa: E402

# Fixture data (invented for the tests) ------------------------------------------------------------------------

CHUNKS = [
    {"chunk_id": "cs301::late::0", "doc_id": "cs301-syllabus", "section": "Late work", "text": "Late work loses 10%."},
    {"chunk_id": "cs301::late::1", "doc_id": "cs301-syllabus", "section": "Late work", "text": "After 3 days: 0."},
    {"chunk_id": "reg::a9::0", "doc_id": "regulation-article-9", "section": "Article 9", "text": "Make-up week."},
    {"chunk_id": "cal::dates::0", "doc_id": "calendar", "section": "Dates", "text": "Make-up week: 11.01.2027."},
    {"chunk_id": "cal::other::0", "doc_id": "calendar", "section": "Other", "text": "Not cited."},
]


def hit(rank: int, chunk_id: str) -> dict:
    row = next(c for c in CHUNKS if c["chunk_id"] == chunk_id)
    return {"rank": rank, "chunk_id": chunk_id, "doc_id": row["doc_id"], "section": row["section"]}


def search(*hits: dict) -> dict:
    return {"step": "search", "prompt_version": None, "model": None, "hits": list(hits)}


def record(case_id: str, text: str, sources: list[dict], trace: list[dict], **change) -> dict:
    output = {
        "intent": "rule_question",
        "classifier": {"intent": "rule_question", "course": None, "urgency": "normal", "multi_step": False},
        "abstain": False,
        "valid": True,
        "answer_text": text,
        "sources": sources,
        "trace": trace,
    }
    rec = {"id": case_id, "error": None, "output": output}
    for key, value in change.items():
        if key == "error":
            rec["error"], rec["output"] = value, None
        elif key == "intent":
            output["classifier"]["intent"] = value
        else:
            output[key] = value
    return rec


LATE = {"doc_id": "cs301-syllabus", "section": "Late work"}
ART9 = {"doc_id": "regulation-article-9", "section": "Article 9"}
DATES = {"doc_id": "calendar", "section": "Dates"}

C1_TEXT = (
    "Late work loses 10 percent per day [1]. After three days it gets 0. [1]\n"
    "Make-up exams are in the make-up week [2]. Please ask your instructor, your advisor or student affairs."
)
C2_TEXT = (
    "Mazeret sınavları 11.01.2027 tarihinde başlar [2].\n"
    "- Haftanın 1. günü sınav yapılır.\n"
    "Bunu ders belgelerinde ya da yönetmelikte bulamadım."
)
RECORDS = [
    # two hits of one section, out of rank order in the file, plus a hit of another section
    record(
        "c1",
        C1_TEXT,
        [LATE, ART9],
        [search(hit(2, "cs301::late::1"), hit(3, "reg::a9::0"), hit(1, "cs301::late::0")), {"step": "answer"}],
    ),
    # two search steps (extraction and answer) that both return the calendar section
    record(
        "c2",
        C2_TEXT,
        [ART9, DATES],
        [
            search(hit(1, "cal::dates::0"), hit(2, "cal::other::0")),
            search(hit(1, "reg::a9::0"), hit(2, "cal::dates::0")),
        ],
    ),
    record("c3", "Fixed reply.", [], [], abstain=True),
    record("c4", "Invalid but has text [1].", [LATE], [search(hit(1, "cs301::late::0"))], valid=False),
    record("c5", "A look-up [1].", [LATE], [search(hit(1, "cs301::late::0"))], intent="lookup"),
    record("c6", "", [], [], error="RuntimeError()"),
]
QUESTIONS = {"c1": "CS-301 late policy?", "c2": "Mazeret sınavı ne zaman?"}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def make_run(
    base: Path, records: list[dict] = RECORDS, chunks_sha: str | None = "match", answer: str = "answer_v2"
) -> Path:
    """A fixture e2e results folder plus its chunks file; fa.CHUNKS must point at base/chunks.jsonl."""
    base.mkdir(parents=True, exist_ok=True)
    write_jsonl(base / "chunks.jsonl", CHUNKS)
    cases = base / "cases.jsonl"
    ids = {r["id"] for r in records}
    write_jsonl(cases, [{"id": i, "text": QUESTIONS.get(i, f"question {i}")} for i in sorted(ids)])
    run = base / "2026-11-24_e2e_w3-real-ansv2_fake"
    run.mkdir(exist_ok=True)
    write_jsonl(run / "outputs.jsonl", records)
    sha = fa.lf_sha256(base / "chunks.jsonl") if chunks_sha == "match" else chunks_sha
    config = {
        "commit": "abc1234",
        "model": {"requested": "fake-model"},
        "prompts": {"answer": answer},
        "cases_path": cases.as_posix(),
        "cases_sha256": fa.lf_sha256(cases),
        "search": {"backend": "real", "chunks_sha256": sha},
    }
    (run / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return run


@pytest.fixture
def run_dir(tmp_path, monkeypatch):
    run = make_run(tmp_path / "fixture")
    monkeypatch.setattr(fa, "CHUNKS", tmp_path / "fixture" / "chunks.jsonl")
    return run


@pytest.fixture
def no_model(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a model client was created")

    monkeypatch.setattr(fa, "OpenAICompatibleClient", refuse)


# Splitter -----------------------------------------------------------------------------------------------------


def test_a_marker_before_or_after_the_period_gives_the_same_claim():
    before = fa.split_claims("Homework 3 is due on 30 November [1]. Late work loses 10% [2].")
    after = fa.split_claims("Homework 3 is due on 30 November. [1] Late work loses 10%. [2]")
    glued = fa.split_claims("Homework 3 is due on 30 November.[1] Late work loses 10%.[2]")
    expected = [
        {"text": "Homework 3 is due on 30 November.", "markers": [1]},
        {"text": "Late work loses 10%.", "markers": [2]},
    ]
    assert before == after == glued == expected


def test_turkish_dates_decimals_ordinals_and_abbreviations_do_not_split():
    text = "Ödev 30.11.2026 tarihine kadar teslim edilir [1]. Notun %2.5 kadarı düşer, örn. bir gün gecikmede [1]. Haftanın 1. günü sınav var [2]!"  # noqa: E501
    assert fa.split_claims(text) == [
        {"text": "Ödev 30.11.2026 tarihine kadar teslim edilir.", "markers": [1]},
        {"text": "Notun %2.5 kadarı düşer, örn. bir gün gecikmede.", "markers": [1]},
        {"text": "Haftanın 1. günü sınav var!", "markers": [2]},
    ]


def test_english_abbreviations_and_decimals_do_not_split():
    text = "Ask Dr. Aydın vs. the office, e.g. by email [1]. The weight is 2.5 points? Yes [2]."
    assert fa.split_claims(text) == [
        {"text": "Ask Dr. Aydın vs. the office, e.g. by email.", "markers": [1]},
        {"text": "The weight is 2.5 points?", "markers": []},
        {"text": "Yes.", "markers": [2]},
    ]


def test_bullets_and_numbered_lines_are_separate_claims_without_their_prefix():
    text = (
        "Rules:\n- Late work loses 10% [1]\n* No work after 3 days [1]\n1. Labs are due Friday [2]\n2) Quiz on Monday"
    )
    assert fa.split_sentences(text)[0]["text"] == "Rules:"  # a heading line: no marker, ends in ":", not a claim
    assert [c["text"] for c in fa.split_claims(text)] == [
        "Late work loses 10%",
        "No work after 3 days",
        "Labs are due Friday",
        "Quiz on Monday",
    ]


def test_a_turkish_ordinal_at_the_start_of_a_line_is_not_a_list_number():
    text = "15. haftada final sınavı yapılır [1].\n3. ödev 30 Kasım'da teslim edilir [2].\n2. Proje raporu [1]"
    assert fa.split_claims(text) == [
        {"text": "15. haftada final sınavı yapılır.", "markers": [1]},
        {"text": "3. ödev 30 Kasım'da teslim edilir.", "markers": [2]},
        {"text": "Proje raporu", "markers": [1]},
    ]


def test_month_and_time_abbreviations_do_not_split():
    text = "The deadline is 30 Nov. 2026 at noon [1]. Submit by 10 a.m. Friday [2]. Sınav 12 Kas. 2026 günü [1]."
    assert fa.split_claims(text) == [
        {"text": "The deadline is 30 Nov. 2026 at noon.", "markers": [1]},
        {"text": "Submit by 10 a.m. Friday.", "markers": [2]},
        {"text": "Sınav 12 Kas. 2026 günü.", "markers": [1]},
    ]


def test_a_line_with_only_markers_belongs_to_the_sentence_before():
    assert fa.split_claims("The exam is on 12 January.\n[2][3]") == [
        {"text": "The exam is on 12 January.", "markers": [2, 3]}
    ]


# Abstention and referral sentences -----------------------------------------------------------------------------


def test_the_fixed_replies_give_no_claims():
    replies = [r for kind in ABSTENTIONS.values() for r in kind.values()]
    replies += [*DECLINE.values(), *OTHER_STUDENT.values()]
    for reply in replies:
        assert fa.split_claims(reply) == [], reply


def test_abstention_and_referral_sentences_are_dropped_after_normalising():
    english = "Late work loses 10% [1].\nPLEASE ASK your instructor,   your advisor or student affairs [1]"
    assert [c["text"] for c in fa.split_claims(english)] == ["Late work loses 10%."]
    turkish = "Geç teslim %10 düşer [1]. " + NOT_FOUND["tr"]
    assert [c["text"] for c in fa.split_claims(turkish)] == ["Geç teslim %10 düşer."]


# Passages, eligibility, markers ----------------------------------------------------------------------------------


def test_rows_come_from_eligible_cases_with_passages_as_retrieved(run_dir):
    rows, prov = fa.build_rows(run_dir)
    assert [r["claim_id"] for r in rows] == ["c1#1", "c1#2", "c1#3", "c2#1", "c2#2"]
    assert prov["eligible_case_ids"] == ["c1", "c2"]  # abstained, invalid, look-up and errored cases are left out
    by_id = {r["claim_id"]: r for r in rows}
    # rank order inside the cited section, and only that section's hits
    assert by_id["c1#1"]["passages"] == "[1] cs301-syllabus · Late work\nLate work loses 10%.\nAfter 3 days: 0."
    assert by_id["c1#3"]["passages"] == "[2] regulation-article-9 · Article 9\nMake-up week."
    assert by_id["c1#1"]["question"] == "CS-301 late policy?"


def test_a_section_found_by_two_search_steps_is_kept_once(run_dir):
    rows, _ = fa.build_rows(run_dir)
    passage = next(r for r in rows if r["claim_id"] == "c2#1")["passages"]
    assert passage == "[2] calendar · Dates\nMake-up week: 11.01.2027."
    assert passage.count("Make-up week: 11.01.2027.") == 1


def test_a_claim_without_a_marker_is_flagged_and_judged_against_every_source(run_dir):
    rows, prov = fa.build_rows(run_dir)
    claim = next(r for r in rows if r["claim_id"] == "c2#2")
    assert claim["claim"] == "Haftanın 1. günü sınav yapılır." and claim["has_marker"] is False
    assert claim["passages"].startswith("[1] regulation-article-9 · Article 9\n")
    assert "\n\n[2] calendar · Dates\n" in claim["passages"]
    assert prov["claims_without_marker"] == 1


def test_a_chunks_file_with_another_sha256_is_refused(run_dir, capsys):
    with fa.CHUNKS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"chunk_id": "new", "doc_id": "x", "section": "y", "text": "z"}) + "\n")
    with pytest.raises(ValueError, match="sha256"):
        fa.build_rows(run_dir)
    assert fa.main(["sheet", "--run", str(run_dir), "--dir", str(run_dir.parent / "out")]) == 1
    assert "sha256" in capsys.readouterr().err
    assert not (run_dir.parent / "out").exists()


def test_a_stub_search_run_is_refused(tmp_path, monkeypatch):
    run = make_run(tmp_path / "stub", chunks_sha=None)
    monkeypatch.setattr(fa, "CHUNKS", tmp_path / "stub" / "chunks.jsonl")
    with pytest.raises(ValueError, match="stub"):
        fa.build_rows(run)


def test_an_answer_v1_run_is_refused(tmp_path, monkeypatch):
    run = make_run(tmp_path / "v1", answer="answer_v1")
    monkeypatch.setattr(fa, "CHUNKS", tmp_path / "v1" / "chunks.jsonl")
    with pytest.raises(ValueError, match="answer_v1"):
        fa.build_rows(run)


def test_a_marker_that_names_no_source_is_refused(tmp_path, monkeypatch):
    bad = record("c1", "Late work loses 10% [3].", [LATE], [search(hit(1, "cs301::late::0"))])
    run = make_run(tmp_path / "bad", [bad])
    monkeypatch.setattr(fa, "CHUNKS", tmp_path / "bad" / "chunks.jsonl")
    with pytest.raises(ValueError, match="names no source"):
        fa.build_rows(run)


# Sample ----------------------------------------------------------------------------------------------------------


def test_more_than_40_claims_are_sampled_with_seed_0_in_file_order():
    picked = fa.sample_indices(45)
    assert len(picked) == 40 and picked == sorted(picked) and picked == fa.sample_indices(45)
    assert fa.sample_indices(12) == list(range(12))
    assert fa.sample_indices(40) == list(range(40))


# Sheet -----------------------------------------------------------------------------------------------------------


def test_sheet_writes_three_files_prints_only_counts_and_never_overwrites(run_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fa, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(fa, "OpenAICompatibleClient", None)  # any model client would fail
    assert fa.main(["sheet", "--run", str(run_dir)]) == 0
    printed = capsys.readouterr()
    assert printed.out.strip() == "cases 2, claims 5 (of 5 eligible), claims without a marker 1"
    assert "fewer than the plan's 20 claims" in printed.err
    out = tmp_path / "results" / f"{date.today().isoformat()}_faithfulness-v1"
    assert sorted(p.name for p in out.iterdir()) == ["labels_rater1.csv", "labels_rater2.csv", "sheet.json"]
    one, two = (fa.read_labels(out / name) for name in ("labels_rater1.csv", "labels_rater2.csv"))
    assert one == two and len(one) == 5 and tuple(one[0]) == fa.COLUMNS
    assert all(r["supported"] == "" and r["note"] == "" for r in one)
    assert [r["has_marker"] for r in one] == ["true", "true", "true", "true", "false"]
    assert one[0]["markers"] == "1"
    meta = json.loads((out / "sheet.json").read_text(encoding="utf-8"))
    assert meta["n"] == 5 and meta["claims_without_marker"] == 1 and "random.Random(0)" in meta["sample_rule"]
    assert meta["meets_plan_minimum"] is False and meta["how_to_label"].startswith(fa.LABEL_RULE)
    before = (out / "labels_rater1.csv").read_bytes()
    assert fa.main(["sheet", "--run", str(run_dir)]) == 1
    assert (out / "labels_rater1.csv").read_bytes() == before


# Blind order ----------------------------------------------------------------------------------------------------


def label(path: Path, values: list[str]) -> None:
    rows = fa.read_labels(path)
    for row, value in zip(rows, values, strict=True):
        row["supported"] = value
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fa.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


R1 = ["true", "true", "false", "true", "false"]
R2 = ["true", "false", "false", "true", "false"]


def labelled_sheet(folder: Path, run: Path, r1: list[str] = R1, r2: list[str] = R2) -> Path:
    assert fa.main(["sheet", "--run", str(run), "--dir", str(folder)]) == 0
    label(folder / "labels_rater1.csv", r1)
    label(folder / "labels_rater2.csv", r2)
    return folder


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A temporary git repository standing in for this one: the label files must be committed in it, under
    results/."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    monkeypatch.setattr(fa, "REPO", root)
    monkeypatch.setattr(fa, "RESULTS_DIR", root / "results")
    return root


def commit(root: Path, *paths: str) -> None:
    _git(root, "add", *(paths or (".",)))
    _git(root, "commit", "-q", "-m", "labels")


RATER_FILES = ["labels_rater1.csv", "labels_rater2.csv"]


@pytest.mark.parametrize("name", RATER_FILES)
def test_run_refuses_an_unlabelled_row_even_when_committed(name, repo, run_dir, capsys, no_model):
    folder = labelled_sheet(repo / "results" / "2026-11-24_faithfulness-v1", run_dir)
    label(folder / name, ["true", "true", "", "true", "false"])
    commit(repo)
    assert fa.main(["run", "--dir", str(folder)]) == 1
    assert f"{name}: supported is not true or false in rows: 3 (c1#3)" in capsys.readouterr().err
    assert not (folder / fa.OUTPUTS).exists()


@pytest.mark.parametrize("name", RATER_FILES)
def test_run_refuses_an_untracked_label_file(name, repo, run_dir, capsys, no_model):
    folder = labelled_sheet(repo / "results" / "2026-11-24_faithfulness-v1", run_dir)
    other = next(n for n in RATER_FILES if n != name)
    commit(repo, f"results/2026-11-24_faithfulness-v1/{other}")
    assert fa.main(["run", "--dir", str(folder)]) == 1
    assert f"{name} is not committed" in capsys.readouterr().err


@pytest.mark.parametrize("name", RATER_FILES)
def test_run_refuses_a_label_file_changed_after_its_commit(name, repo, run_dir, capsys, no_model):
    folder = labelled_sheet(repo / "results" / "2026-11-24_faithfulness-v1", run_dir)
    commit(repo)
    assert all(fa.labels_git_state(folder / n, repo)[0] is None for n in RATER_FILES)
    label(folder / name, ["false"] * 5)
    assert fa.main(["run", "--dir", str(folder)]) == 1
    assert f"{name} has uncommitted changes" in capsys.readouterr().err


def test_run_refuses_label_files_committed_in_two_commits(repo, run_dir, capsys, no_model):
    folder = labelled_sheet(repo / "results" / "2026-11-24_faithfulness-v1", run_dir)
    commit(repo, "results/2026-11-24_faithfulness-v1/labels_rater1.csv")
    commit(repo)
    assert fa.main(["run", "--dir", str(folder)]) == 1
    assert "different commits" in capsys.readouterr().err


@pytest.mark.parametrize("name", RATER_FILES)
def test_run_refuses_a_changed_claim(name, repo, run_dir, capsys, no_model):
    folder = labelled_sheet(repo / "results" / "2026-11-24_faithfulness-v1", run_dir)
    rows = fa.read_labels(folder / name)
    rows[1]["claim"] = "After two days it gets 0."
    with (folder / name).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fa.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    commit(repo)
    assert fa.main(["run", "--dir", str(folder)]) == 1
    assert f"{name}: claim or passages changed in rows: c1#2" in capsys.readouterr().err


def test_a_real_run_refuses_label_files_outside_results(repo, run_dir, capsys, no_model):
    folder = labelled_sheet(repo / "elsewhere", run_dir)
    commit(repo)
    assert fa.main(["run", "--dir", str(folder)]) == 1
    assert "under results/" in capsys.readouterr().err


def test_a_dry_run_inside_results_is_refused(run_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fa, "RESULTS_DIR", tmp_path / "results")
    folder = labelled_sheet(tmp_path / "results" / "2026-11-24_faithfulness-v1", run_dir)
    capsys.readouterr()
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 1
    assert "a dry run needs --dir outside results/" in capsys.readouterr().err


def test_a_dry_run_also_refuses_an_unlabelled_row(run_dir, tmp_path, capsys):
    folder = labelled_sheet(tmp_path / "sheet", run_dir, r2=["true", "", "false", "true", "false"])
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 1
    assert "labels_rater2.csv: supported is not true or false in rows: 2 (c1#2)" in capsys.readouterr().err
    assert not (folder / "config.json").exists()


def test_a_new_run_never_replaces_the_config_of_an_earlier_run(run_dir, tmp_path, capsys):
    folder = labelled_sheet(tmp_path / "sheet", run_dir)
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 0
    config = (folder / "config.json").read_bytes()
    (folder / fa.OUTPUTS).unlink()  # outputs removed, labels then changed: still refused
    label(folder / "labels_rater1.csv", ["false"] * 5)
    capsys.readouterr()
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 1
    assert "never replaced" in capsys.readouterr().err
    assert (folder / "config.json").read_bytes() == config


# Judge calls ----------------------------------------------------------------------------------------------------


class ScriptedJudge(FakeClient):
    def __init__(self, replies: list, model: str = "fake-judge", returned: str | None = None):
        super().__init__(model)
        self.replies, self.returned, self.calls = list(replies), returned or model, 0

    def chat(self, messages, temperature):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, LLMResponse):
            return reply
        return LLMResponse(reply, self.returned, 10, 10, 0.0, model_requested=self.model)


def judge_one(client) -> dict:
    system, template = fa.load_judge_prompt(fa.PROMPT_VERSION)
    return fa.judge_claim(client, system, template, "q?", "a claim", "[1] d · s\ntext")


def test_one_retry_after_an_invalid_reply():
    client = ScriptedJudge(['{"supported": "yes"}', '<think>{x}</think>{"supported": false}'])
    result = judge_one(client)
    assert client.calls == 2 and result["valid"] and result["supported"] is False


def test_invalid_twice_gives_null_never_a_guess():
    client = ScriptedJudge(["not json", '{"verdict": true}'])
    result = judge_one(client)
    assert client.calls == 2 and result == {"valid": False, "supported": None, "attempts": result["attempts"]}


def test_the_prompt_holds_the_smoke_example_and_the_placeholders():
    text = (ROOT / "prompts" / "faithfulness_v1.md").read_text(encoding="utf-8")
    for value in fa.SMOKE.values():
        assert value in text
    _, template = fa.load_judge_prompt(fa.PROMPT_VERSION)
    assert all(f"{{{k}}}" in template for k in ("question", "claim", "passages"))
    message = fa.user_message(template, "Q {claim}", "C", "P")
    assert "Q {claim}" in message and "<claim>\nC\n</claim>" in message


# Kappa and the decision rule ------------------------------------------------------------------------------------


def labels(values: list[bool]) -> list[dict]:
    return [
        {
            "claim_id": f"x#{i}",
            "case_id": f"x{i // 3}",
            "claim": f"claim {i}",
            "has_marker": "true",
            "supported": str(v).lower(),
        }  # noqa: E501
        for i, v in enumerate(values)
    ]


def records(values: list[bool | None]) -> list[dict]:
    return [
        {"claim_id": f"x#{i}", "case_id": f"x{i // 3}", "valid": v is not None, "supported": v, "attempts": []}
        for i, v in enumerate(values)
    ]


CONFIG = {
    "commit": "abc",
    "model": {"requested": "m", "returned": ["m"]},
    "prompt_version": "faithfulness_v1",
    "temperature": 0.0,
    "labels": {"rater1": {"sha256": "1" * 64}, "rater2": {"sha256": "2" * 64}},
    "labels_commit": "abc",
    "sheet": {"run": "results/x", "eligible_claims": 10, "sampled": False},
    "complete": True,
}
T, F = True, False
RATER1 = [T, T, T, T, T, T, F, F, F, F]
RATER2 = [T, T, T, T, T, F, F, F, F, F]


def test_three_kappas_and_the_judge_branch_on_known_values():
    report = fa.kappa_report(labels(RATER1), labels(RATER2), records(RATER1), CONFIG)
    pairs = report["pairs"]
    # judge = rater 1: p_o 1. judge vs rater 2: p_o 0.9, p_e 0.6*0.5 + 0.4*0.5 = 0.5, kappa 0.8; same for the raters
    assert pairs["judge_vs_rater1"]["cohen_kappa"] == 1.0
    assert pairs["judge_vs_rater2"]["cohen_kappa"] == 0.8
    assert pairs["rater1_vs_rater2"]["cohen_kappa"] == 0.8
    assert pairs["judge_vs_rater2"]["raw_agreement"]["k"] == 9
    assert pairs["judge_vs_rater2"]["confusion_matrix"]["rater2_unsupported"] == {
        "judge_supported": 1,
        "judge_unsupported": 4,
        "judge_invalid": 0,
    }
    assert pairs["rater1_vs_rater2"]["confusion_matrix"]["rater1_supported"] == {
        "rater2_supported": 5,
        "rater2_unsupported": 1,
    }
    assert all(len(p["kappa_ci95_bootstrap"]) == 2 for p in pairs.values())
    assert report["for_reporting"] and report["judge_meets_threshold_against_both"]
    u = report["unsupported_claims"]
    assert u["source"] == "judge" and (u["k"], u["n"]) == (4, 10) and u["judge_invalid"] == 0
    assert (u["worst_case"]["k"], u["worst_case"]["n"]) == (4, 10)
    assert [(d["claim_id"], d["case_id"], d["claim"]) for d in report["disagreements"]] == [("x#5", "x1", "claim 5")]
    assert report["disagreements"][0]["pairs"] == ["judge_vs_rater2", "rater1_vs_rater2"]


def test_below_the_threshold_the_human_union_decides_and_an_invalid_reply_disagrees():
    judge = [T, T, T, T, T, T, T, T, F, None]
    report = fa.kappa_report(labels(RATER1), labels(RATER2), records(judge), CONFIG)
    pairs = report["pairs"]
    # the invalid reply takes the opposite of each rater (true here); vs rater 1: p_o 0.7, p_e 0.9*0.6 + 0.1*0.4
    assert pairs["judge_vs_rater1"]["raw_agreement"]["k"] == 7
    assert pairs["judge_vs_rater1"]["cohen_kappa"] == round((0.7 - 0.58) / 0.42, 4)
    assert pairs["judge_vs_rater2"]["cohen_kappa"] == 0.2  # p_o 0.6, p_e 0.5
    assert pairs["judge_vs_rater1"]["confusion_matrix"]["rater1_unsupported"]["judge_invalid"] == 1
    assert report["invalid_judge_rows"] == 1 and not report["judge_meets_threshold_against_both"]
    u = report["unsupported_claims"]
    assert u["source"] == "human" and "reason" in u
    assert (u["k"], u["n"]) == (5, 10)  # either rater: claims 5-9
    assert (u["rater1"]["k"], u["rater1"]["n"]) == (4, 10)
    assert (u["rater2"]["k"], u["rater2"]["n"]) == (5, 10)
    assert (u["agreed_only"]["k"], u["agreed_only"]["n"]) == (4, 9)
    invalid = next(d for d in report["disagreements"] if d["claim_id"] == "x#9")
    assert invalid["judge"] is None and invalid["pairs"] == ["judge_vs_rater1", "judge_vs_rater2"]


def test_an_invalid_reply_is_left_out_of_n_in_the_judge_branch_and_shown_in_the_worst_case():
    rater = [T] * 8 + [F] * 4
    judge = [T] * 8 + [F] * 3 + [None]
    report = fa.kappa_report(labels(rater), labels(rater), records(judge), CONFIG)
    assert report["pairs"]["judge_vs_rater1"]["raw_agreement"]["k"] == 11
    u = report["unsupported_claims"]
    assert u["source"] == "judge" and (u["k"], u["n"]) == (3, 11) and u["judge_invalid"] == 1
    assert (u["worst_case"]["k"], u["worst_case"]["n"]) == (4, 12)


def test_kappa_is_not_for_reporting_when_another_model_answered():
    config = {**CONFIG, "model": {"requested": "m", "returned": ["m", "other"]}}
    report = fa.kappa_report(labels(RATER1), labels(RATER2), records(RATER1), config)
    assert not report["for_reporting"] and "models returned" in report["not_for_reporting_reasons"][0]


# End to end -----------------------------------------------------------------------------------------------------


def test_dry_run_then_kappa_end_to_end(run_dir, tmp_path, capsys):
    folder = labelled_sheet(tmp_path / "sheet", run_dir)
    before = {n: (folder / n).read_bytes() for n in RATER_FILES}
    capsys.readouterr()
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 0
    printed = capsys.readouterr().out
    assert "true" not in printed.lower() and "false" not in printed.lower()  # never a verdict
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    assert config["n_calls"] == 1 + 5 and config["complete"] and config["smoke"][0]["valid"]
    assert {k: v["sha256"] for k, v in config["labels"].items()} == {
        "rater1": fa.lf_sha256(folder / "labels_rater1.csv"),
        "rater2": fa.lf_sha256(folder / "labels_rater2.csv"),
    }
    assert config["not_for_reporting_reasons"] and "random.Random(0)" in config["sample_rule"]

    assert fa.main(["kappa", "--dir", str(folder)]) == 0
    assert {n: (folder / n).read_bytes() for n in RATER_FILES} == before  # run and kappa never write the labels
    report = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    # the fake judge says every claim is supported; rater 1 has 3 true of 5, rater 2 2 of 5
    assert report["pairs"]["judge_vs_rater1"]["raw_agreement"]["k"] == 3
    assert report["pairs"]["judge_vs_rater1"]["cohen_kappa"] == 0.0
    assert report["pairs"]["rater1_vs_rater2"]["raw_agreement"]["k"] == 4
    assert report["unsupported_claims"]["source"] == "human"
    assert (report["unsupported_claims"]["k"], report["unsupported_claims"]["n"]) == (3, 5)
    assert report["claims_without_marker"] == 1 and not report["for_reporting"]
    summary = (folder / "summary.md").read_text(encoding="utf-8")
    assert summary.startswith("**NOT FOR REPORTING**") and "c1#2" in summary
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 1  # outputs exist, no --resume


def test_kappa_refuses_labels_changed_after_the_run(run_dir, tmp_path):
    folder = labelled_sheet(tmp_path / "sheet", run_dir)
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 0
    label(folder / "labels_rater2.csv", ["true"] * 5)
    assert fa.main(["kappa", "--dir", str(folder)]) == 1


def test_smoke_call_with_another_model_stops_the_run(run_dir, tmp_path, monkeypatch, capsys):
    folder = labelled_sheet(tmp_path / "sheet", run_dir)
    monkeypatch.setattr(fa, "DryRunJudgeClient", lambda: ScriptedJudge(['{"supported": false}'], returned="other"))
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 1
    assert "not switched" in capsys.readouterr().err
    assert not (folder / fa.OUTPUTS).exists()


class FailOnCall(fa.DryRunJudgeClient):
    """The offline judge, but call number `fail_at` returns an API error."""

    def __init__(self, fail_at: int):
        super().__init__()
        self.fail_at, self.n = fail_at, 0

    def chat(self, messages, temperature):
        self.n += 1
        if self.n == self.fail_at:
            return LLMResponse("", self.model, 0, 0, 0.0, error="RateLimitError()", model_requested=self.model)
        return super().chat(messages, temperature)


def test_an_api_error_stops_the_run_and_resume_finishes_it(run_dir, tmp_path, monkeypatch):
    folder = labelled_sheet(tmp_path / "sheet", run_dir)
    monkeypatch.setattr(fa, "DryRunJudgeClient", lambda: FailOnCall(4))  # smoke + 2 claims, then an error
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 1
    assert len(fa.load_jsonl(folder / fa.OUTPUTS)) == 2  # the failed claim is not recorded
    assert fa.main(["kappa", "--dir", str(folder)]) == 1  # outputs do not cover every claim
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 1  # needs --resume
    monkeypatch.setattr(fa, "DryRunJudgeClient", lambda: FailOnCall(0))
    assert fa.main(["run", "--dry-run", "--resume", "--dir", str(folder)]) == 0
    outputs = fa.load_jsonl(folder / fa.OUTPUTS)
    assert sorted(r["claim_id"] for r in outputs) == ["c1#1", "c1#2", "c1#3", "c2#1", "c2#2"]
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    assert config["complete"] and config["call_errors"] == 1 and config["n_calls"] == 4 + 4
    assert len(config["sessions"]) == 2 and len(config["smoke"]) == 2
    assert fa.main(["kappa", "--dir", str(folder)]) == 0


def test_resume_refuses_changed_labels(run_dir, tmp_path, monkeypatch, capsys):
    folder = labelled_sheet(tmp_path / "sheet", run_dir)
    monkeypatch.setattr(fa, "DryRunJudgeClient", lambda: FailOnCall(3))
    assert fa.main(["run", "--dry-run", "--dir", str(folder)]) == 1
    label(folder / "labels_rater1.csv", ["false"] * 5)
    assert fa.main(["run", "--dry-run", "--resume", "--dir", str(folder)]) == 1
    assert "labels" in capsys.readouterr().err
