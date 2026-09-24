"""Verify each provider adapter normalizes raw SDK exceptions consistently.

Uses MagicMock(spec=<real SDK exception class>) so `isinstance()` checks in
the adapters' `normalize_error()` pass without needing real network
responses or API keys.
"""

from unittest.mock import MagicMock

import anthropic
import groq
import openai
import pytest

from providers.anthropic_provider import AnthropicAdapter
from providers.errors import (
    BlogForgeLLMError,
    ContextWindowExceededError,
    InvalidAPIKeyError,
    ProviderUnavailableError,
    RateLimitExceededError,
)
from providers.groq_provider import GroqAdapter
from providers.openai_provider import OpenAIAdapter


def _fake_exc(sdk_cls, message, status_code=None, retry_after=None):
    exc = MagicMock(spec=sdk_cls)
    exc.__str__.return_value = message
    if status_code is not None:
        exc.status_code = status_code
    exc.response = MagicMock()
    exc.response.headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    return exc


ADAPTERS = [
    (AnthropicAdapter(), anthropic),
    (OpenAIAdapter(), openai),
    (GroqAdapter(), groq),
]


@pytest.mark.parametrize("adapter,sdk", ADAPTERS)
def test_authentication_error_maps_to_invalid_api_key(adapter, sdk):
    exc = _fake_exc(sdk.AuthenticationError, "invalid api key")
    normalized = adapter.normalize_error(exc)
    assert isinstance(normalized, InvalidAPIKeyError)
    assert not normalized.retryable


@pytest.mark.parametrize("adapter,sdk", ADAPTERS)
def test_rate_limit_error_is_retryable_with_retry_after(adapter, sdk):
    exc = _fake_exc(sdk.RateLimitError, "rate limited", retry_after=5)
    normalized = adapter.normalize_error(exc)
    assert isinstance(normalized, RateLimitExceededError)
    assert normalized.retryable
    assert normalized.retry_after == 5.0


@pytest.mark.parametrize("adapter,sdk", ADAPTERS)
def test_bad_request_context_length_maps_to_context_window_error(adapter, sdk):
    exc = _fake_exc(sdk.BadRequestError, "maximum context length exceeded")
    normalized = adapter.normalize_error(exc)
    assert isinstance(normalized, ContextWindowExceededError)
    assert not normalized.retryable


@pytest.mark.parametrize("adapter,sdk", ADAPTERS)
def test_connection_error_is_retryable_provider_unavailable(adapter, sdk):
    exc = _fake_exc(sdk.APIConnectionError, "connection failed")
    normalized = adapter.normalize_error(exc)
    assert isinstance(normalized, ProviderUnavailableError)
    assert normalized.retryable


@pytest.mark.parametrize("adapter,sdk", ADAPTERS)
def test_server_error_5xx_is_retryable_provider_unavailable(adapter, sdk):
    exc = _fake_exc(sdk.APIStatusError, "server error", status_code=503)
    normalized = adapter.normalize_error(exc)
    assert isinstance(normalized, ProviderUnavailableError)
    assert normalized.retryable


@pytest.mark.parametrize("adapter,sdk", ADAPTERS)
def test_unrecognized_exception_falls_back_to_generic_non_retryable_error(adapter, sdk):
    exc = RuntimeError("something else entirely")
    normalized = adapter.normalize_error(exc)
    assert isinstance(normalized, BlogForgeLLMError)
    assert not normalized.retryable


@pytest.mark.parametrize("adapter,sdk", ADAPTERS)
def test_user_message_never_contains_the_word_traceback(adapter, sdk):
    exc = _fake_exc(sdk.RateLimitError, "rate limited")
    normalized = adapter.normalize_error(exc)
    assert "Traceback" not in normalized.user_message
    assert "File \"" not in normalized.user_message
