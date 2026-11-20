"""One model call that must return a JSON object matching a pydantic schema: temperature 0, one retry.

Shared by the classifier, the extraction step and the answer step, so all three validate, retry and trace the
same way. The retry sends the validation error back to the model; a failed API call is not retried here (the
client already waits and retries on rate limits).
"""

import json
import re
from pathlib import Path

from pydantic import BaseModel, ValidationError

from aic390.llm import ChatClient

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
TEMPERATURE = 0.0
MAX_ATTEMPTS = 2  # the first call plus one retry


def load_prompt(version: str) -> str:
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def parse_json(text: str, schema: type[BaseModel]) -> BaseModel:
    """The first {...} block in the reply, checked against the schema. Raises ValueError on any problem."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError("no JSON object in the reply")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ValueError(f"schema: {problems}") from exc


def call_json(
    client: ChatClient,
    system: str,
    user: str,
    schema: type[BaseModel],
    step: str,
    prompt_version: str,
) -> tuple[BaseModel | None, list[dict]]:
    """Returns (validated output or None, trace). None means both attempts failed; the caller decides the fallback."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    trace = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        resp = client.chat(messages, temperature=TEMPERATURE)
        record = {
            "step": step,
            "attempt": attempt,
            "prompt_version": prompt_version,
            "model": resp.model,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "latency_s": resp.latency_s,
            "error": resp.error,
        }
        trace.append(record)
        if resp.error is not None:
            break
        try:
            return parse_json(resp.text, schema), trace
        except ValueError as exc:
            record["error"] = str(exc)
            messages += [
                {"role": "assistant", "content": resp.text},
                {"role": "user", "content": f"Your reply was not valid ({exc}). Reply with the JSON object only."},
            ]
    return None, trace
