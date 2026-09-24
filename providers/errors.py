"""Provider-independent, application-level LLM errors.

`nodes.py` and `app.py` only ever see these — raw provider SDK
exceptions are caught and normalized inside each `providers/*_provider.py`
adapter's `normalize_error()`. This keeps error handling in the
workflow/UI layer completely decoupled from which provider raised the
original exception.

`user_message` is always safe to show directly in the Streamlit UI: it
never contains an API key, and never contains a raw stack trace.
"""

from typing import Optional


class BlogForgeLLMError(Exception):
    """Base class for all normalized LLM/provider errors."""

    def __init__(self, user_message: str, *, retryable: bool = False, technical_detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.retryable = retryable
        self.technical_detail = technical_detail or user_message


class MissingAPIKeyError(BlogForgeLLMError):
    """No API key was supplied for the selected provider."""


class InvalidAPIKeyError(BlogForgeLLMError):
    """The provider rejected the API key (authentication failure)."""


class RateLimitExceededError(BlogForgeLLMError):
    """The provider's rate limit (requests or tokens per minute/day) was hit."""

    def __init__(self, user_message: str, *, retry_after: Optional[float] = None, technical_detail: str = ""):
        super().__init__(user_message, retryable=True, technical_detail=technical_detail)
        self.retry_after = retry_after


class ContextWindowExceededError(BlogForgeLLMError):
    """The request (prompt + requested output) exceeded the model's context window."""


class UnsupportedModelError(BlogForgeLLMError):
    """The requested model ID is invalid or not available to this account."""


class ProviderUnavailableError(BlogForgeLLMError):
    """A transient provider-side failure (timeout, connection error, 5xx)."""

    def __init__(self, user_message: str, technical_detail: str = ""):
        super().__init__(user_message, retryable=True, technical_detail=technical_detail)
