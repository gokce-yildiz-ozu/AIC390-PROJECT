"""W1.6: tokens per request and $ per 1,000 requests, from a finished run's outputs.jsonl.

Offline: reads saved outputs, never calls a model.

    python scripts/cost_breakdown.py results/2026-11-16_baseline_openai-gpt-oss-120b
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aic390.cost import load_prices, request_cost  # noqa: E402


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = round(q * (len(ordered) - 1))
    return ordered[index]


def describe(records: list[dict], prices: dict) -> dict:
    costs = [request_cost(r["model"], r["input_tokens"], r["output_tokens"], prices) for r in records]
    reasoning = [r.get("reasoning_tokens") or 0 for r in records]
    output = [r["output_tokens"] for r in records]
    model = records[0]["model"]
    reasoning_cost = sum(reasoning) * prices[model]["output_usd_per_mtok"] / 1_000_000
    return {
        "n": len(records),
        "mean_input_tokens": statistics.mean(r["input_tokens"] for r in records),
        "mean_output_tokens": statistics.mean(output),
        "mean_reasoning_tokens": statistics.mean(reasoning),
        "p50_total_tokens": percentile([r["input_tokens"] + r["output_tokens"] for r in records], 0.5),
        "p95_total_tokens": percentile([r["input_tokens"] + r["output_tokens"] for r in records], 0.95),
        "usd_per_1000_requests": 1000 * statistics.mean(costs),
        "share_of_cost_from_reasoning": reasoning_cost / sum(costs),
    }


def breakdown(records: list[dict], key) -> dict:
    groups = defaultdict(list)
    for r in records:
        groups[key(r)].append(r)
    return groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--inputs", type=Path, default=Path("eval/testsets/week1_inputs.jsonl"))
    args = parser.parse_args()

    prices = load_prices()
    records = [json.loads(line) for line in (args.run_dir / "outputs.jsonl").read_text(encoding="utf-8").splitlines()]
    records = [r for r in records if r.get("error") is None]
    channel = {
        row["id"]: row["channel"] for row in map(json.loads, args.inputs.read_text(encoding="utf-8").splitlines())
    }

    result = {
        "source": str(args.run_dir / "outputs.jsonl"),
        "model": records[0]["model"],
        "price": {
            k: prices[records[0]["model"]][k]
            for k in ("input_usd_per_mtok", "output_usd_per_mtok", "source", "checked")
        },
        "formula": "cost = (input_tokens * input_price + output_tokens * output_price) / 1e6; "
        "output_tokens include reasoning",
        "all": describe(records, prices),
        "by_temperature": {
            str(t): describe(g, prices) for t, g in sorted(breakdown(records, lambda r: r["temperature"]).items())
        },
        "by_channel": {
            c: describe(g, prices) for c, g in sorted(breakdown(records, lambda r: channel[r["id"]]).items())
        },
    }
    out = args.run_dir / "cost_breakdown.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nwrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
