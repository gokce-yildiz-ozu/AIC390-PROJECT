"""W2.1 request classifier: one JSON object per input, temperature 0, validated, one retry.

Interface 1 (docs/STATUS.md): {"intent", "course", "urgency", "multi_step"}. `classify` adds `valid` and `trace`
so the harness and the demo can show what happened; neither is graded.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aic390 import jsoncall
from aic390.llm import ChatClient

PROMPT_VERSION = "classifier_v1"
COURSE_PATTERN = r"^[A-Z]{2,5}-\d{3}$"

Intent = Literal["deadline_message", "rule_question", "lookup", "reminder", "other"]

FALLBACK = {"intent": "other", "course": None, "urgency": "normal", "multi_step": False}


class ClassifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Intent
    course: str | None = Field(pattern=COURSE_PATTERN)
    urgency: Literal["high", "normal"]
    multi_step: bool = False


def load_prompt(version: str = PROMPT_VERSION) -> str:
    return jsoncall.load_prompt(version)


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
    return jsoncall.parse_json(text, ClassifierOutput)


def classify(case: dict, client: ChatClient, prompt_version: str = PROMPT_VERSION) -> dict:
    output, trace = jsoncall.call_json(
        client, load_prompt(prompt_version), format_input(case), ClassifierOutput, "classifier", prompt_version
    )
    if output is None:
        return {**FALLBACK, "valid": False, "trace": trace}
    return {**output.model_dump(), "valid": True, "trace": trace}
