"""Verify llm.py's provider dispatch and bounded-retry behavior.

Provider SDK classes are monkeypatched with fakes, so no real API keys or
network access are required.
"""

import anthropic
import pytest
from pydantic import BaseModel

import llm
import providers.anthropic_provider as anthropic_provider
from providers.errors import MissingAPIKeyError, RateLimitExceededError


class DummyOutput(BaseModel):
    value: str


def _real_rate_limit_error(message="rate limited"):
    # Real anthropic.RateLimitError instances require an httpx.Response to
    # construct normally; bypass __init__ and set only what the adapter's
    # normalize_error() reads (str(exc), exc.response.headers).
    exc = anthropic.RateLimitError.__new__(anthropic.RateLimitError)
    exc.args = (message,)

    class _FakeResponse:
        headers = {}

    exc.response = _FakeResponse()
    return exc


class _FakeStructuredRunnable:
    def __init__(self, results):
        self._results = list(results)

    def invoke(self, messages):
        result = self._results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class _FakeChatModel:
    def __init__(self, structured_results):
        self._structured_results = structured_results

    def with_structured_output(self, model_cls, method=None):
        return _FakeStructuredRunnable(self._structured_results)


def test_get_llm_dispatches_to_the_anthropic_adapter(monkeypatch):
    captured = {}

    class FakeChatAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(anthropic_provider, "ChatAnthropic", FakeChatAnthropic)

    result = llm.get_llm(provider="anthropic", model="claude-sonnet-5", api_key="sk-test", max_tokens=123)

    assert isinstance(result, FakeChatAnthropic)
    assert captured["model"] == "claude-sonnet-5"
    assert captured["max_tokens"] == 123
    assert captured["api_key"] == "sk-test"


def test_get_llm_raises_missing_api_key_error_when_blank():
    with pytest.raises(MissingAPIKeyError):
        llm.get_llm(provider="anthropic", model="claude-sonnet-5", api_key="   ", max_tokens=100)


def test_get_llm_raises_missing_api_key_error_when_none():
    with pytest.raises(MissingAPIKeyError):
        llm.get_llm(provider="anthropic", model="claude-sonnet-5", api_key=None, max_tokens=100)


def test_invoke_structured_retries_once_then_succeeds(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)

    fake_model = _FakeChatModel([_real_rate_limit_error(), {"value": "ok"}])
    monkeypatch.setattr(anthropic_provider, "ChatAnthropic", lambda **kw: fake_model)

    result = llm.invoke_structured(
        DummyOutput,
        [("human", "hi")],
        provider="anthropic",
        model="claude-sonnet-5",
        api_key="sk-test",
        max_tokens=100,
        max_retries=2,
    )

    assert result.value == "ok"


def test_invoke_structured_raises_normalized_error_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)

    fake_model = _FakeChatModel([_real_rate_limit_error(), _real_rate_limit_error()])
    monkeypatch.setattr(anthropic_provider, "ChatAnthropic", lambda **kw: fake_model)

    with pytest.raises(RateLimitExceededError):
        llm.invoke_structured(
            DummyOutput,
            [("human", "hi")],
            provider="anthropic",
            model="claude-sonnet-5",
            api_key="sk-test",
            max_tokens=100,
            max_retries=1,
        )


def test_invoke_structured_never_retries_more_than_max_retries(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(llm.time, "sleep", lambda d: sleep_calls.append(d))

    # 3 failures queued, but max_retries=1 should mean at most 1 retry
    # (2 total attempts) before raising — the 3rd failure is never consumed.
    fake_model = _FakeChatModel(
        [_real_rate_limit_error(), _real_rate_limit_error(), _real_rate_limit_error()]
    )
    monkeypatch.setattr(anthropic_provider, "ChatAnthropic", lambda **kw: fake_model)

    with pytest.raises(RateLimitExceededError):
        llm.invoke_structured(
            DummyOutput,
            [("human", "hi")],
            provider="anthropic",
            model="claude-sonnet-5",
            api_key="sk-test",
            max_tokens=100,
            max_retries=1,
        )

    assert len(sleep_calls) == 1  # exactly one retry attempted
    assert fake_model._structured_results  # the 3rd queued failure was never consumed
