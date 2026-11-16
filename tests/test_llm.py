from types import SimpleNamespace

import httpx2
import openai

from aic390.llm import OpenAICompatibleClient


def _rate_limit(retry_after: str | None) -> openai.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    request = httpx2.Request("POST", "http://test.invalid/chat/completions")
    response = httpx2.Response(429, headers=headers, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


def _completion(reasoning_tokens: int | None = 30):
    details = SimpleNamespace(reasoning_tokens=reasoning_tokens) if reasoning_tokens is not None else None
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50, completion_tokens_details=details)
    message = SimpleNamespace(content="ok", model_extra={"reasoning": "thinking"})
    return SimpleNamespace(model="provider/model-name", usage=usage, choices=[SimpleNamespace(message=message)])


class StubCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    def create(self, **kwargs):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _client(outcomes, slept):
    client = OpenAICompatibleClient(
        model="configured/id", api_key="test", base_url="http://test.invalid", sleep=slept.append
    )
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=StubCompletions(outcomes)))
    return client


def test_rate_limit_waits_retry_after_and_is_recorded():
    slept = []
    resp = _client([_rate_limit("2"), _completion()], slept).chat([{"role": "user", "content": "x"}], 0.0)
    assert resp.error is None
    assert slept == [2.0]
    assert resp.retries == 1 and resp.retry_wait_s == 2.0
    assert resp.model == "provider/model-name"
    assert resp.model_requested == "configured/id"
    assert (resp.input_tokens, resp.output_tokens, resp.reasoning_tokens) == (100, 50, 30)
    assert resp.reasoning == "thinking"


def test_rate_limit_gives_up_after_max_retries_without_raising():
    slept = []
    resp = _client([_rate_limit(None)] * 4, slept).chat([{"role": "user", "content": "x"}], 0.0)
    assert resp.error is not None and "RateLimitError" in resp.error
    assert resp.retries == 3 and len(slept) == 3


def test_unreported_reasoning_tokens_stay_null():
    resp = _client([_completion(reasoning_tokens=None)], []).chat([{"role": "user", "content": "x"}], 0.0)
    assert resp.reasoning_tokens is None
