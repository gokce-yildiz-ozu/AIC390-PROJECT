"""W1.5 baseline: one prompt on every input at several temperatures.

    python scripts/run_baseline.py --dry-run                     # offline, fake model, free
    python scripts/run_baseline.py --inputs eval/testsets/week1_inputs.jsonl --ids w1-01,w1-12 --temperatures 0
    python scripts/run_baseline.py --inputs eval/testsets/week1_inputs.jsonl --sleep 12 --yes

Writes results/<date>_baseline[-trial]_<model>/{config.json, outputs.jsonl, summary.json, grading.csv}.
outputs.jsonl is appended record by record, so a crash keeps every finished call.
"""

import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

from aic390.cost import load_prices, request_cost
from aic390.llm import ChatClient, FakeClient, OpenAICompatibleClient

BUDGET_WITHOUT_ASKING = 50
GRADING_COLUMNS = ["id", "temperature", "ingredients", "expected", "output", "label", "note"]
CODE_PATHS = ("src", "scripts", "prompts", "config")


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        return out.stdout.strip() or "uncommitted"
    except OSError:
        return "unknown"


def git_dirty_files(paths: tuple[str, ...] = CODE_PATHS, cwd: Path | None = None) -> list[str] | None:
    """Tracked files under `paths` that differ from HEAD (staged or not). None if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "diff", "HEAD", "--name-only", "--", *paths], capture_output=True, text=True, cwd=cwd
        )
    except OSError:
        return None
    if out.returncode != 0:
        return None
    return [line for line in out.stdout.splitlines() if line.strip()]


def load_inputs(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if "id" not in row or "text" not in row:
            raise ValueError(f"{path}: every line needs 'id' and 'text': {row}")
    return rows


def select_inputs(inputs: list[dict], ids: list[str] | None, limit: int | None) -> list[dict]:
    if ids:
        by_id = {row["id"]: row for row in inputs}
        unknown = [i for i in ids if i not in by_id]
        if unknown:
            raise ValueError(f"unknown input ids: {', '.join(unknown)}")
        inputs = [by_id[i] for i in ids]
    return inputs[:limit] if limit is not None else inputs


def build_user_message(row: dict) -> str:
    """What the user's app knows about a message, then the message. Labels (ingredients, expected) stay out."""
    header = [
        f"channel: {row.get('channel') or 'none'}",
        f"received_at: {row.get('received_at') or 'none'}",
        f"course: {row.get('course') or 'none'}",
        f"sender: {row.get('sender') or 'none'}",
    ]
    return "\n".join(header) + "\n\n" + row["text"]


def run(
    client: ChatClient,
    inputs: list[dict],
    system_prompt: str,
    temperatures: list[float],
    prices: dict | None,
    on_record: Callable[[dict], None] | None = None,
    sleep_s: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    price = prices.get(client.model) if prices is not None else None
    if prices is not None and price is None:
        print(
            f"warning: no price for {client.model!r} in config/prices.json; cost_usd will be null",
            file=sys.stderr,
        )
    records = []
    for temp in temperatures:
        for row in inputs:
            if records and sleep_s > 0:
                sleep(sleep_s)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": build_user_message(row)},
            ]
            resp = client.chat(messages, temperature=temp)
            cost = None
            if price is not None and resp.error is None:
                cost = request_cost(client.model, resp.input_tokens, resp.output_tokens, {client.model: price})
            record = {
                "id": row["id"],
                "temperature": temp,
                "ingredients": row.get("ingredients", []),
                **resp.to_dict(),
                "cost_usd": cost,
            }
            records.append(record)
            if on_record is not None:
                on_record(record)
    return records


def compare_temperatures(records: list[dict], temperatures: list[float]) -> dict[str, str]:
    """Per input: are the outputs at every temperature identical? A first 'what changed' signal."""
    by_id: dict[str, list[dict]] = {}
    for r in records:
        by_id.setdefault(r["id"], []).append(r)
    status = {}
    for input_id, rs in by_id.items():
        if len(rs) < len(temperatures) or any(r["error"] is not None for r in rs):
            status[input_id] = "incomplete"
            continue
        distinct = len({r["text"] for r in rs})
        status[input_id] = "identical" if distinct == 1 else f"differ ({distinct} distinct / {len(rs)})"
    return status


def summarize(records: list[dict], temperatures: list[float] | None = None) -> dict:
    ok = [r for r in records if r["error"] is None]
    summary: dict = {
        "requests": len(records),
        "succeeded": len(ok),
        "failed": len(records) - len(ok),
        "total_retries": sum(r.get("retries", 0) for r in records),
    }
    if ok:
        totals = [r["input_tokens"] + r["output_tokens"] for r in ok]
        reasoning = [r.get("reasoning_tokens") for r in ok]
        summary["mean_input_tokens"] = statistics.mean(r["input_tokens"] for r in ok)
        summary["mean_output_tokens"] = statistics.mean(r["output_tokens"] for r in ok)
        summary["mean_reasoning_tokens"] = statistics.mean(reasoning) if all(x is not None for x in reasoning) else None
        summary["mean_total_tokens"] = statistics.mean(totals)
        summary["max_total_tokens"] = max(totals)
        summary["total_tokens"] = sum(totals)
        summary["latency_p50_s"] = statistics.median(r["latency_s"] for r in ok)
        costs = [r["cost_usd"] for r in ok if r["cost_usd"] is not None]
        complete = len(costs) == len(ok)
        # Paid-tier list price applied to measured tokens; not what we were charged on the free plan.
        summary["cost_usd_at_list_price"] = sum(costs) if complete else None
        summary["usd_per_1000_requests"] = 1000 * statistics.mean(costs) if complete else None
    if temperatures and len(temperatures) > 1:
        status = compare_temperatures(records, temperatures)
        summary["n_inputs_identical_across_temperatures"] = sum(s == "identical" for s in status.values())
    return summary


def write_grading(path: Path, records: list[dict], inputs: list[dict]) -> None:
    order = {row["id"]: i for i, row in enumerate(inputs)}
    by_id = {row["id"]: row for row in inputs}
    rows = sorted(records, key=lambda r: (order.get(r["id"], len(order)), r["temperature"]))
    # utf-8-sig so Excel on Windows shows Turkish characters correctly.
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(GRADING_COLUMNS)
        for r in rows:
            row = by_id.get(r["id"], {})
            output = r["text"] if r["error"] is None else f"[error] {r['error']}"
            writer.writerow(
                [r["id"], r["temperature"], ";".join(r.get("ingredients", [])), row.get("expected", ""), output, "", ""]
            )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inputs", type=Path, default=Path("eval/testsets/example_inputs.jsonl"))
    ap.add_argument("--prompt", type=Path, default=Path("prompts/baseline_v1.md"))
    ap.add_argument("--temperatures", type=float, nargs="+", default=[0.0, 0.7, 1.2])
    ap.add_argument(
        "--ids",
        type=lambda s: [x.strip() for x in s.split(",") if x.strip()],
        default=None,
        help="comma-separated input ids to run (trial)",
    )
    ap.add_argument("--limit", type=int, default=None, help="run only the first N (selected) inputs (trial)")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between calls, for free-tier rate limits")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true", help="use the offline fake model")
    ap.add_argument("--yes", action="store_true", help="skip the paid-call budget prompt")
    args = ap.parse_args()

    try:
        inputs = select_inputs(load_inputs(args.inputs), args.ids, args.limit)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    n_calls = len(inputs) * len(args.temperatures)
    client: ChatClient = FakeClient() if args.dry_run else OpenAICompatibleClient()
    prices = None if args.dry_run else load_prices()

    if not args.dry_run and n_calls > BUDGET_WITHOUT_ASKING and not args.yes:
        answer = input(f"{n_calls} paid calls to {client.model}. Continue? [y/N] ")
        if answer.strip().lower() != "y":
            return 1

    trial = args.ids is not None or args.limit is not None
    slug = "dryrun" if args.dry_run else client.model.replace("/", "-")
    name = f"{date.today().isoformat()}_baseline{'-trial' if trial else ''}_{slug}"
    out = args.out or Path("results") / name
    outputs_path = out / "outputs.jsonl"
    if outputs_path.exists() and outputs_path.stat().st_size > 0:
        print(f"error: {outputs_path} already has results; pass --out to write elsewhere", file=sys.stderr)
        return 1
    out.mkdir(parents=True, exist_ok=True)

    dirty_files = git_dirty_files()
    if dirty_files:
        print(
            "warning: uncommitted changes, so this run is not reproducible from the recorded commit: "
            + ", ".join(dirty_files),
            file=sys.stderr,
        )
    config = {
        "commit": git_commit(),
        "dirty": bool(dirty_files) if dirty_files is not None else None,
        "model": client.model,
        "prompt": str(args.prompt),
        "prompt_version": args.prompt.stem,
        "inputs": str(args.inputs),
        "ids": [row["id"] for row in inputs] if trial else None,
        "n_inputs": len(inputs),
        "temperatures": args.temperatures,
        "n_calls": n_calls,
        "sleep_s": args.sleep,
        "price": prices.get(client.model) if prices is not None else None,
    }
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with outputs_path.open("w", encoding="utf-8") as f:

        def append(record: dict) -> None:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

        records = run(
            client,
            inputs,
            args.prompt.read_text(encoding="utf-8"),
            args.temperatures,
            prices,
            on_record=append,
            sleep_s=args.sleep,
        )

    summary = summarize(records, args.temperatures)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_grading(out / "grading.csv", records, inputs)

    if len(args.temperatures) > 1:
        for input_id, status in compare_temperatures(records, args.temperatures).items():
            print(f"{input_id}  {status}")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
