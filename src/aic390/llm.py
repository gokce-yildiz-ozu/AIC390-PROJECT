"""Provider-agnostic chat client.

Any provider with an OpenAI-compatible endpoint works (Gemini, Groq, OpenRouter, a local
server). Switching provider is a change in .env, not in code, so every experiment records
exactly which model and endpoint produced it.
"""

import os
import time
from dataclasses import asdict, dataclass
from typing import Protocol

from dotenv import load_dotenv


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class ChatClient(Protocol):
    model: str

    def chat(self, messages: list[dict], temperature: float) -> LLMResponse: ...


class OpenAICompatibleClient:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float = 60.0,
        max_retries: int = 3,
    ):
        from openai import OpenAI

        load_dotenv()
        self.model = model or os.environ["LLM_MODEL"]
        self._client = OpenAI(
            base_url=base_url or os.environ.get("LLM_BASE_URL") or None,
            api_key=api_key or os.environ["LLM_API_KEY"],
            timeout=timeout_s,
            max_retries=max_retries,
        )

    def chat(self, messages: list[dict], temperature: float) -> LLMResponse:
        start = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(model=self.model, messages=messages, temperature=temperature)
        except Exception as exc:  # recorded, never silently dropped: failures are data
            return LLMResponse("", self.model, 0, 0, time.perf_counter() - start, repr(exc))
        usage = resp.usage
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            model=resp.model or self.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_s=time.perf_counter() - start,
        )


class FakeClient:
    """Deterministic offline client for tests and dry runs; costs nothing."""

    def __init__(self, model: str = "fake-model"):
        self.model = model

    def chat(self, messages: list[dict], temperature: float) -> LLMResponse:
        prompt = " ".join(m["content"] for m in messages)
        return LLMResponse(
            text=f"[fake t={temperature}] {messages[-1]['content'][:40]}",
            model=self.model,
            input_tokens=len(prompt) // 4,
            output_tokens=12,
            latency_s=0.0,
        )
