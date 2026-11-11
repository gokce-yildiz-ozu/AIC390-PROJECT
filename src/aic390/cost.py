"""Dollar cost from token counts. Prices come from config/prices.json, never from memory."""

import json
from pathlib import Path

PRICES_PATH = Path("config/prices.json")


def load_prices(path: Path = PRICES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["models"]


def request_cost(model: str, input_tokens: int, output_tokens: int, prices: dict) -> float:
    if model not in prices:
        raise KeyError(
            f"No price for {model!r} in config/prices.json. Add it from the provider's pricing page, with the "
            "source URL and the date you checked."
        )
    p = prices[model]
    return (input_tokens * p["input_usd_per_mtok"] + output_tokens * p["output_usd_per_mtok"]) / 1_000_000
