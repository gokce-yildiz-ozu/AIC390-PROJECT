"""W2.1 request classifier: one JSON object per input, temperature 0, validated, one retry.

Interface 1 (docs/STATUS.md): {"intent", "course", "urgency", "multi_step"}. `classify` adds `valid` and `trace`
so the harness and the demo can show what happened; neither is graded.
"""

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aic390.llm import ChatClient

PROMPT_VERSION = "classifier_v1"
PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
TEMPERATURE = 0.0
MAX_ATTEMPTS = 2  # the first call plus one retry

Intent = Literal["deadline_message", "rule_question", "lookup", "reminder", "other"]

FALLBACK = {"intent": "other", "course": None, "urgency": "normal", "multi_step": False}


class ClassifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    course: str | None = Field(pattern=r"^[A-Z]{2,5}-\d{3}$")
    urgency: Literal["high", "normal"]
    multi_step: bool = False


def load_prompt(version: str = PROMPT_VERSION) -> str:
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def format_input(case: dict) -> str:
    """Channel metadata, then the text. Labels (expected, ingredients) never reach the model."""
    header = [
        f"channel: {case.get('channel') or 'none'}",
        f"received_at: {case.get('received_at') or 'none'}",
        f"course: {case.get('course') or 'none'}",
        f"sender: {case.get('sender') or 'none'}",
    ]
    return "\n".join(header) + "\n\n" + case["text"]


def parse(text: str) -> ClassifierOutput:
    """The first {...} block in the reply, checked against the schema. Raises ValueError on any problem."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise ValueError("no JSON object in the reply")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    try:
        return ClassifierOutput.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ValueError(f"schema: {problems}") from exc


def classify(case: dict, client: ChatClient, prompt_version: str = PROMPT_VERSION) -> dict:
    messages = [
        {"role": "system", "content": load_prompt(prompt_version)},
        {"role": "user", "content": format_input(case)},
    ]
    trace = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        resp = client.chat(messages, temperature=TEMPERATURE)
        step = {
            "step": "classifier",
            "attempt": attempt,
            "prompt_version": prompt_version,
            "model": resp.model,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "latency_s": resp.latency_s,
            "error": resp.error,
        }
        trace.append(step)
        if resp.error is not None:
            break  # a failed API call is not retried here; the client already retried rate limits
        try:
            output = parse(resp.text)
        except ValueError as exc:
            step["error"] = str(exc)
            messages += [
                {"role": "assistant", "content": resp.text},
                {"role": "user", "content": f"Your reply was not valid ({exc}). Reply with the JSON object only."},
            ]
            continue
        return {**output.model_dump(), "valid": True, "trace": trace}
    return {**FALLBACK, "valid": False, "trace": trace}
