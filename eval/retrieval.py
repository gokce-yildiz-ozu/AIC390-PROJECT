"""W3.5 retrieval evaluation and the W3.7 ablations: the frozen retrieval questions through interface 2.

    python eval/retrieval.py                                  # main configuration: hybrid + reranker (W3.5)
    python eval/retrieval.py --mode dense                     # ablation 1
    python eval/retrieval.py --mode bm25                      # ablation 1, extra row
    python eval/retrieval.py --no-rerank                      # ablation 2
    python eval/retrieval.py --compare results/A results/B --metric hit_at_5     # paired exact McNemar
    python eval/retrieval.py --fake --label smoke             # offline fake models: checks the script, not reportable

Writes results/<date>_retrieval_<label>/{config.json, per_question.jsonl, summary.json, summary.md}; the label
defaults to <mode>-rerank or <mode>-norerank, as in the plan rows in docs/STATUS.md.
Scoring (eval/testsets/README.md): a hit is any gold (doc_id, section) in the top k; all@k needs every gold
passage; MRR uses the rank of the first gold passage in the top 10 (0 if none). Search is called with
course=None and the row's as_of. No model call: the embedder and the reranker only score text.

The terminal and summary.md show numbers and question ids only. per_question.jsonl holds the gold and the retrieved
passages for the failure analysis (W3.8); the corpus author does not open it (D-009).
"""

import argparse
import json
import platform
import random
import re
import statistics
import sys
import time
import zlib
from datetime import date
from pathlib import Path

from run_e2e import RESULTS_DIR, ROOT, TESTSETS_README, git_commit, git_untracked, lf_sha256, rel

from aic390.stats import _percentile, mcnemar_exact, proportion_ci

sys.path.insert(0, str(ROOT / "scripts"))
from run_baseline import git_dirty_files  # noqa: E402

SCRIPT = "eval/retrieval.py"
DEFAULT_QUESTIONS = ROOT / "eval" / "testsets" / "retrieval_questions.jsonl"
DIRTY_PATHS = ("src", "eval", "scripts", "data")
KS = (1, 3, 5, 10)
TOP = max(KS)
KINDS = ("direct", "paraphrase", "confusable", "version", "multi")
LANGUAGES = ("en", "tr")
WARM_UP_QUERY = "warm-up query, not timed"
COMPARE_METRICS = tuple(f"hit_at_{k}" for k in KS) + tuple(f"all_at_{k}" for k in KS)


# Scoring ---------------------------------------------------------------------------------------------------------


def gold_ranks(gold: list[dict], hits: list[dict]) -> list[int | None]:
    """1-based rank of each gold passage in the hit list (its first chunk), None if it is not there."""
    ranks = []
    for g in gold:
        positions = [
            i for i, h in enumerate(hits, start=1) if (h["doc_id"], h["section"]) == (g["doc_id"], g["section"])
        ]
        ranks.append(positions[0] if positions else None)
    return ranks


def score_question(gold: list[dict], hits: list[dict]) -> dict:
    ranks = gold_ranks(gold, hits)
    found = [r for r in ranks if r is not None]
    first = min(found) if found else None
    scores = {"gold_ranks": ranks, "first_gold_rank": first, "reciprocal_rank": 1.0 / first if first else 0.0}
    for k in KS:
        scores[f"hit_at_{k}"] = first is not None and first <= k
        scores[f"all_at_{k}"] = all(r is not None and r <= k for r in ranks)
    return scores


def proportion(k: int, n: int) -> dict:
    if n == 0:
        return {"k": 0, "n": 0, "value": None, "ci95_wilson": None}
    low, high = proportion_ci(k, n, method="wilson")
    return {"k": k, "n": n, "value": round(k / n, 4), "ci95_wilson": [round(low, 4), round(high, 4)]}


def mean_bootstrap_ci(values: list[float], n_resamples: int = 2000, seed: int = 0) -> list[float] | None:
    """Percentile bootstrap 95% interval of the mean, resampling questions with replacement."""
    if not values:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_resamples))
    return [round(_percentile(means, 0.025), 4), round(_percentile(means, 0.975), 4)]


def metrics(records: list[dict], bootstrap: bool = True) -> dict:
    out = {"n": len(records)}
    for k in KS:
        out[f"hit_at_{k}"] = proportion(sum(r[f"hit_at_{k}"] for r in records), len(records))
    rr = [r["reciprocal_rank"] for r in records]
    out["mrr"] = {
        "value": round(statistics.fmean(rr), 4) if rr else None,
        "ci95_bootstrap": mean_bootstrap_ci(rr) if bootstrap else None,
    }
    return out


def summarize(records: list[dict], config: dict) -> dict:
    multi = [r for r in records if r["kind"] == "multi"]
    latencies = [r["latency_s"] for r in records]
    summary = {
        "label": config["label"],
        "reportable": not config["problems"],
        "problems": config["problems"],
        "conditions": conditions_text(config),
        "overall": metrics(records),
        "multi_all_at_k": {f"all_at_{k}": proportion(sum(r[f"all_at_{k}"] for r in multi), len(multi)) for k in KS},
        "by_kind": {kind: metrics([r for r in records if r["kind"] == kind], False) for kind in KINDS},
        "by_language": {lang: metrics([r for r in records if r["language"] == lang], False) for lang in LANGUAGES},
        "latency_s": {
            "median": round(statistics.median(latencies), 4) if latencies else None,
            "p90": round(_percentile(sorted(latencies), 0.9), 4) if latencies else None,
            "note": "per search call, after one untimed warm-up query; index build not included",
        },
        "misses_at_5": [r["id"] for r in records if not r["hit_at_5"]],
        "model_calls": 0,
    }
    for group in (summary["by_kind"], summary["by_language"]):
        for name in [name for name, m in group.items() if m["n"] == 0]:
            del group[name]
    return summary


# Run conditions --------------------------------------------------------------------------------------------------


def recorded_sha256(questions: Path, readme: Path = TESTSETS_README) -> str | None:
    """The hash in the eval/testsets/README.md section whose heading names the file (the freeze line, R9)."""
    if not readme.exists():
        return None
    for section in re.split(r"(?m)^## ", readme.read_text(encoding="utf-8"))[1:]:
        if f"`{questions.name}`" in section.split("\n", 1)[0]:
            match = re.search(r"\b[0-9a-f]{64}\b", section)
            return match.group(0) if match else None
    return None


def model_revision(name: str) -> str | None:
    """Commit hash of the locally cached Hugging Face model (the main ref), so a run names its exact weights."""
    try:
        from huggingface_hub import scan_cache_dir

        for repo in scan_cache_dir().repos:
            if repo.repo_id == name:
                refs = {ref: rev.commit_hash for rev in repo.revisions for ref in rev.refs}
                return refs.get("main") or next(iter(refs.values()), None)
    except Exception:  # noqa: BLE001 - the revision is recorded when it can be found; the run does not depend on it
        return None
    return None


def device_name() -> str:
    try:
        import torch

        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu (no torch)"


def package_versions() -> dict:
    versions = {"python": platform.python_version()}
    for name in ("numpy", "bm25s", "torch", "sentence_transformers", "transformers"):
        try:
            versions[name] = __import__(name).__version__
        except ImportError:
            versions[name] = None
    return versions


def conditions_text(config: dict) -> str:
    s = config["search"]
    models = "fake models" if config["fake"] else f"{s['embedding_model']} + {s['reranker_model']}"
    rerank = "reranker on" if s["rerank"] else "reranker off"
    return (
        f"{s['mode']}, {rerank}, top {s['top_n']} per list, RRF k = {s['rrf_k']}, {models}, "
        f"{config['chunks']['n_chunks']} chunks, course=None, as_of from the question, device {config['device']}"
    )


def problems_for(config: dict) -> list[str]:
    problems = []
    if config["fake"]:
        problems.append("fake embedder and reranker (--fake)")
    if not config["questions"]["frozen"]:
        problems.append("questions do not match their recorded sha256")
    if config["dirty"] is None or config["untracked"] is None:
        problems.append("git state unknown")
    if config["dirty"]:
        problems.append("uncommitted changes: " + ", ".join(config["dirty"]))
    if config["untracked"]:
        problems.append("not in the commit: " + ", ".join(config["untracked"]))
    if config["subset"]:
        problems.append("subset of the questions (--limit)")
    return problems


# Search ----------------------------------------------------------------------------------------------------------


class FakeEmbedder:
    """Hashed bag of words: lets the script run offline (CI, smoke test). Its numbers mean nothing."""

    def encode(self, texts):
        import numpy as np

        from aic390.rag.search import tokenize

        vectors = np.zeros((len(texts), 256), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in tokenize(text):
                vectors[row, zlib.crc32(token.encode()) % 256] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1, norms)


class FakeReranker:
    def score(self, query, texts):
        from aic390.rag.search import tokenize

        wanted = set(tokenize(query))
        return [len(wanted & set(tokenize(t))) / max(len(wanted), 1) for t in texts]


def build_search(chunks: list[dict], mode: str, rerank: bool, fake: bool):
    from aic390.rag.search import CrossEncoderReranker, HybridSearch, default_embedder

    embedder = None
    if mode != "bm25":
        embedder = FakeEmbedder() if fake else default_embedder()
    reranker = None
    if rerank:
        reranker = FakeReranker() if fake else CrossEncoderReranker()
    return HybridSearch(chunks, embedder=embedder, reranker=reranker, mode=mode, rerank=rerank)


# Commands --------------------------------------------------------------------------------------------------------


def load_questions(path: Path) -> list[dict]:
    raw = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def run(args: argparse.Namespace) -> Path:
    from aic390.rag import search as rag

    label = args.label or f"{args.mode}-{'rerank' if args.rerank else 'norerank'}"
    out_dir = args.results_dir / f"{date.today().isoformat()}_retrieval_{label}"
    if out_dir.exists() and not args.overwrite:
        raise SystemExit(f"{rel(out_dir)} exists; use another --label or --overwrite")

    questions = load_questions(args.questions)
    if args.limit:
        questions = questions[: args.limit]
    chunks = rag.load_chunks(args.chunks)
    recorded = recorded_sha256(args.questions)
    actual = lf_sha256(args.questions)

    config = {
        "script": SCRIPT,
        "date": date.today().isoformat(),
        "label": label,
        "git_commit": git_commit(),
        "dirty": git_dirty_files(DIRTY_PATHS, cwd=ROOT),
        "untracked": git_untracked([Path(__file__), args.questions, args.chunks]),
        "questions": {
            "path": rel(args.questions),
            "sha256": actual,
            "recorded_sha256": recorded,
            "frozen": recorded == actual,
            "n": len(questions),
        },
        "subset": bool(args.limit),
        "chunks": {"path": rel(args.chunks), "sha256": lf_sha256(args.chunks), "n_chunks": len(chunks)},
        "search": {
            "mode": args.mode,
            "rerank": args.rerank,
            "top_n": 20,
            "rrf_k": 60,
            "k": TOP,
            "course": None,
            "embedding_model": None if args.mode == "bm25" else rag.EMBEDDING_MODEL,
            "embedding_revision": None,
            "reranker_model": rag.RERANKER_MODEL if args.rerank else None,
            "reranker_revision": None,
        },
        "fake": args.fake,
        "device": "fake" if args.fake else device_name(),
        "packages": package_versions(),
    }

    start = time.perf_counter()
    engine = build_search(chunks, args.mode, args.rerank, args.fake)
    config["index_build_s"] = round(time.perf_counter() - start, 2)
    if not args.fake:
        s = config["search"]
        s["embedding_revision"] = model_revision(s["embedding_model"]) if s["embedding_model"] else None
        s["reranker_revision"] = model_revision(s["reranker_model"]) if s["reranker_model"] else None
    config["problems"] = problems_for(config)

    engine.search(WARM_UP_QUERY, k=TOP)
    records = []
    for q in questions:
        t0 = time.perf_counter()
        hits = engine.search(q["question"], course=None, k=TOP, as_of=q.get("as_of"))
        latency = time.perf_counter() - t0
        records.append(
            {
                "id": q["id"],
                "kind": q["kind"],
                "language": q["language"],
                "as_of": q.get("as_of"),
                "gold": q["gold"],
                **score_question(q["gold"], hits),
                "latency_s": round(latency, 4),
                "retrieved": [
                    {
                        key: h[key]
                        for key in ("doc_id", "section", "chunk_id", "score", "bm25_rank", "dense_rank", "rerank_score")
                    }
                    for h in hits
                ],
            }
        )

    summary = summarize(records, config)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "config.json", config)
    write_json(out_dir / "summary.json", summary)
    with (out_dir / "per_question.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for r in records:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out_dir / "summary.md").write_text(summary_markdown(summary, config), encoding="utf-8", newline="\n")
    print(summary_markdown(summary, config))
    print(f"Written to {rel(out_dir)}")
    return out_dir


def compare(a_dir: Path, b_dir: Path, metric: str, results_dir: Path) -> dict:
    """Paired exact McNemar on one per-question metric; b = right only in A, c = right only in B."""
    configs = [json.loads((d / "config.json").read_text(encoding="utf-8")) for d in (a_dir, b_dir)]
    runs = [{r["id"]: r for r in map(json.loads, open_lines(d / "per_question.jsonl"))} for d in (a_dir, b_dir)]
    problems = []
    if configs[0]["questions"]["sha256"] != configs[1]["questions"]["sha256"]:
        problems.append("the two runs used different question files")
    if configs[0]["chunks"]["sha256"] != configs[1]["chunks"]["sha256"]:
        problems.append("the two runs used different chunks")
    if set(runs[0]) != set(runs[1]):
        problems.append("the two runs have different question ids")
    if problems:
        raise SystemExit("cannot compare: " + "; ".join(problems))

    ids = sorted(runs[0])
    only_a = [i for i in ids if runs[0][i][metric] and not runs[1][i][metric]]
    only_b = [i for i in ids if runs[1][i][metric] and not runs[0][i][metric]]
    latency = [statistics.median(r[i]["latency_s"] for i in ids) for r in runs]
    result = {
        "a": rel(a_dir),
        "b": rel(b_dir),
        "metric": metric,
        "n": len(ids),
        "a_correct": sum(runs[0][i][metric] for i in ids),
        "b_correct": sum(runs[1][i][metric] for i in ids),
        "b_count": len(only_a),
        "c_count": len(only_b),
        "only_a_ids": only_a,
        "only_b_ids": only_b,
        "mcnemar_exact_p": round(mcnemar_exact(len(only_a), len(only_b)), 4),
        "note": "with b + c < 6 no split can reach p < 0.05" if len(only_a) + len(only_b) < 6 else None,
        "median_latency_s": {"a": round(latency[0], 4), "b": round(latency[1], 4)},
        "same_device": configs[0]["device"] == configs[1]["device"],
        "reportable": not (configs[0]["problems"] or configs[1]["problems"]),
    }
    name = f"{date.today().isoformat()}_retrieval-compare_{configs[0]['label']}_vs_{configs[1]['label']}_{metric}"
    out = results_dir / name
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "compare.json", result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Written to {rel(out)}")
    return result


# Output ----------------------------------------------------------------------------------------------------------


def open_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _fmt(p: dict) -> str:
    if p["value"] is None:
        return "n = 0"
    low, high = p["ci95_wilson"]
    return f"{p['k']}/{p['n']} = {p['value']:.3f} [{low:.3f}, {high:.3f}]"


def summary_markdown(summary: dict, config: dict) -> str:
    o = summary["overall"]
    mrr = o["mrr"]
    ci = mrr["ci95_bootstrap"]
    lines = [
        f"# Retrieval run `{summary['label']}`",
        "",
        f"Conditions: {summary['conditions']}.",
        f"Questions: `{config['questions']['path']}` (sha256 `{config['questions']['sha256'][:12]}…`, "
        f"n = {o['n']}). Chunks sha256 `{config['chunks']['sha256'][:12]}…`. Commit `{config['git_commit']}`.",
        "",
        "Reportable: yes" if summary["reportable"] else "**Not for reporting:** " + "; ".join(summary["problems"]),
        "",
        "| Metric | Value, Wilson 95% |",
        "|---|---|",
        *[f"| hit@{k} | {_fmt(o[f'hit_at_{k}'])} |" for k in KS],
        f"| MRR (top {TOP}) | {mrr['value']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] bootstrap |"
        if ci
        else "| MRR | not computed |",
        *[f"| all@{k}, multi questions | {_fmt(summary['multi_all_at_k'][f'all_at_{k}'])} |" for k in (5, 10)],
        "",
        "| Group | n | hit@1 | hit@5 | MRR |",
        "|---|---|---|---|---|",
    ]
    for group in ("by_kind", "by_language"):
        for name, m in summary[group].items():
            lines.append(
                f"| {name} | {m['n']} | {m['hit_at_1']['value']:.3f} | {m['hit_at_5']['value']:.3f} "
                f"| {m['mrr']['value']:.3f} |"
            )
    lat = summary["latency_s"]
    lines += [
        "",
        f"Search latency per query: median {lat['median']} s, p90 {lat['p90']} s ({lat['note']}). "
        f"Index build {config['index_build_s']} s.",
        "No gold passage in the top 5 (W3.8 failure table): " + (", ".join(summary["misses_at_5"]) or "none") + ".",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=("hybrid", "dense", "bm25"), default="hybrid")
    ap.add_argument("--no-rerank", dest="rerank", action="store_false", help="ablation 2: no reranker")
    ap.add_argument("--label", help="results folder label; default <mode>-rerank or <mode>-norerank")
    ap.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    ap.add_argument("--chunks", type=Path, default=None, help="default data/chunks.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="first N questions only (not reportable)")
    ap.add_argument("--fake", action="store_true", help="fake embedder and reranker, offline (not reportable)")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    ap.add_argument("--compare", nargs=2, type=Path, metavar=("A", "B"), help="two results folders of this script")
    ap.add_argument("--metric", choices=COMPARE_METRICS, default="hit_at_5", help="for --compare")
    args = ap.parse_args(argv)

    if args.compare:
        compare(args.compare[0], args.compare[1], args.metric, args.results_dir)
        return 0
    if args.chunks is None:
        from aic390.rag.search import DEFAULT_CHUNKS

        args.chunks = DEFAULT_CHUNKS
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
