"""Provider-agnostic chat client.

Any provider with an OpenAI-compatible endpoint works (Gemini, Groq, OpenRouter, a local
server). Switching provider is a change in .env, not in code, so every experiment records
exactly which model and endpoint produced it.
"""

import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol

from dotenv import load_dotenv

DEFAULT_RETRY_AFTER_S = 10.0


@dataclass
class LLMResponse:
    text: str
    model: str  # as returned by the provider; may differ from the configured id
    input_tokens: int
    output_tokens: int  # includes reasoning tokens for reasoning models
    latency_s: float  # last attempt only; rate-limit waits are in retry_wait_s
    error: str | None = None
    model_requested: str | None = None
    reasoning_tokens: int | None = None  # None = the provider did not report it
    reasoning: str | None = None
    retries: int = 0
    retry_wait_s: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class ChatClient(Protocol):
    model: str

    def chat(self, messages: list[dict], temperature: float) -> LLMResponse: ...


def _retry_after_s(exc: Exception) -> float:
    response = getattr(exc, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    try:
        return float(value) if value is not None else DEFAULT_RETRY_AFTER_S
    except ValueError:
        return DEFAULT_RETRY_AFTER_S


class OpenAICompatibleClient:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float = 60.0,
        max_rate_limit_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ):
        from openai import OpenAI

        load_dotenv()
        self.model = model or os.environ["LLM_MODEL"]
        self.max_rate_limit_retries = max_rate_limit_retries
        self._sleep = sleep
        # SDK retries are off so that every 429 and its wait are counted in the record.
        self._client = OpenAI(
            base_url=base_url or os.environ.get("LLM_BASE_URL") or None,
            api_key=api_key or os.environ["LLM_API_KEY"],
            timeout=timeout_s,
            max_retries=0,
        )

    def chat(self, messages: list[dict], temperature: float) -> LLMResponse:
        from openai import RateLimitError

        retries, waited = 0, 0.0
        while True:
            start = time.perf_counter()
            try:
                resp = self._client.chat.completions.create(
                    model=self.model, messages=messages, temperature=temperature
                )
                break
            except RateLimitError as exc:
                if retries >= self.max_rate_limit_retries:
                    return self._failure(exc, start, retries, waited)
                wait = _retry_after_s(exc)
                self._sleep(wait)
                retries += 1
                waited += wait
            except Exception as exc:  # recorded, never silently dropped: failures are data
                return self._failure(exc, start, retries, waited)
        latency = time.perf_counter() - start

        usage = resp.usage
        details = getattr(usage, "completion_tokens_details", None) if usage else None
        message = resp.choices[0].message
        extra = message.model_extra or {}
        return LLMResponse(
            text=message.content or "",
            model=resp.model or self.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_s=latency,
            model_requested=self.model,
            reasoning_tokens=getattr(details, "reasoning_tokens", None) if details else None,
            reasoning=extra.get("reasoning"),
            retries=retries,
            retry_wait_s=waited,
        )

    def _failure(self, exc: Exception, start: float, retries: int, waited: float) -> LLMResponse:
        return LLMResponse(
            "",
            self.model,
            0,
            0,
            time.perf_counter() - start,
            repr(exc),
            model_requested=self.model,
            retries=retries,
            retry_wait_s=waited,
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
            model_requested=self.model,
        )
