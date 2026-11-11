"""W1.5 baseline: one prompt on every input at several temperatures.

    python scripts/run_baseline.py --dry-run                     # offline, fake model, free
    python scripts/run_baseline.py --inputs eval/testsets/week1_inputs.jsonl

Writes results/<date>_baseline_<model>/{config.json, outputs.jsonl, summary.json}.
"""

import argparse
import json
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path

from aic390.cost import load_prices, request_cost
from aic390.llm import ChatClient, FakeClient, OpenAICompatibleClient

BUDGET_WITHOUT_ASKING = 50


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        return out.stdout.strip() or "uncommitted"
    except OSError:
        return "unknown"


def load_inputs(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if "id" not in row or "text" not in row:
            raise ValueError(f"{path}: every line needs 'id' and 'text': {row}")
    return rows


def run(
    client: ChatClient,
    inputs: list[dict],
    system_prompt: str,
    temperatures: list[float],
    prices: dict | None,
) -> list[dict]:
    records = []
    for temp in temperatures:
        for row in inputs:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": row["text"]},
            ]
            resp = client.chat(messages, temperature=temp)
            cost = None
            if prices is not None and resp.error is None:
                cost = request_cost(client.model, resp.input_tokens, resp.output_tokens, prices)
            records.append(
                {
                    "id": row["id"],
                    "temperature": temp,
                    "ingredients": row.get("ingredients", []),
                    **resp.to_dict(),
                    "cost_usd": cost,
                }
            )
    return records


def summarize(records: list[dict]) -> dict:
    ok = [r for r in records if r["error"] is None]
    summary: dict = {"requests": len(records), "succeeded": len(ok), "failed": len(records) - len(ok)}
    if ok:
        summary["mean_input_tokens"] = statistics.mean(r["input_tokens"] for r in ok)
        summary["mean_output_tokens"] = statistics.mean(r["output_tokens"] for r in ok)
        summary["latency_p50_s"] = statistics.median(r["latency_s"] for r in ok)
        costs = [r["cost_usd"] for r in ok if r["cost_usd"] is not None]
        if len(costs) == len(ok):
            summary["spend_usd"] = sum(costs)
            summary["usd_per_1000_requests"] = 1000 * statistics.mean(costs)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inputs", type=Path, default=Path("eval/testsets/example_inputs.jsonl"))
    ap.add_argument("--prompt", type=Path, default=Path("prompts/baseline_v1.md"))
    ap.add_argument("--temperatures", type=float, nargs="+", default=[0.0, 0.7, 1.2])
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true", help="use the offline fake model")
    ap.add_argument("--yes", action="store_true", help="skip the paid-call budget prompt")
    args = ap.parse_args()

    inputs = load_inputs(args.inputs)
    n_calls = len(inputs) * len(args.temperatures)
    client: ChatClient = FakeClient() if args.dry_run else OpenAICompatibleClient()
    prices = None if args.dry_run else load_prices()

    if not args.dry_run and n_calls > BUDGET_WITHOUT_ASKING and not args.yes:
        answer = input(f"{n_calls} paid calls to {client.model}. Continue? [y/N] ")
        if answer.strip().lower() != "y":
            return 1

    records = run(client, inputs, args.prompt.read_text(encoding="utf-8"), args.temperatures, prices)
    summary = summarize(records)

    slug = "dryrun" if args.dry_run else client.model.replace("/", "-")
    out = args.out or Path("results") / f"{date.today().isoformat()}_baseline_{slug}"
    out.mkdir(parents=True, exist_ok=True)
    config = {
        "commit": git_commit(),
        "model": client.model,
        "prompt": str(args.prompt),
        "inputs": str(args.inputs),
        "n_inputs": len(inputs),
        "temperatures": args.temperatures,
    }
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    with (out / "outputs.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
