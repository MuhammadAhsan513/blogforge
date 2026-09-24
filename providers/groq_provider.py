"""Groq provider adapter (the free-tier provider)."""

from langchain_groq import ChatGroq

from providers.base import ProviderAdapter
from providers.errors import (
    BlogForgeLLMError,
    ContextWindowExceededError,
    InvalidAPIKeyError,
    ProviderUnavailableError,
    RateLimitExceededError,
    UnsupportedModelError,
)


class GroqAdapter(ProviderAdapter):
    display_name = "Groq"

    def build_chat_model(self, model_id: str, api_key: str, max_tokens: int) -> ChatGroq:
        return ChatGroq(
            model=model_id,
            api_key=api_key,
            max_tokens=max_tokens,
            max_retries=0,  # BlogForge does its own bounded retries in llm.py
        )

    def structured_output_method(self, model_id: str) -> str:
        # Groq implements structured output via tool-calling.
        return "function_calling"

    def normalize_error(self, exc: Exception) -> BlogForgeLLMError:
        import groq

        if isinstance(exc, groq.AuthenticationError):
            return InvalidAPIKeyError(
                "Groq rejected the API key. Double-check the key in the sidebar "
                "(get a free one at console.groq.com/keys).",
                technical_detail=str(exc),
            )
        if isinstance(exc, groq.RateLimitError):
            return RateLimitExceededError(
                "Groq's free-tier rate limit was hit for this model. Wait a moment and try "
                "again, or switch to a lighter free model (e.g. Llama 3.1 8B Instant) in the "
                "sidebar.",
                retry_after=_retry_after_seconds(exc),
                technical_detail=str(exc),
            )
        if isinstance(exc, groq.NotFoundError):
            return UnsupportedModelError(
                "The selected Groq model is not available.",
                technical_detail=str(exc),
            )
        if isinstance(exc, groq.BadRequestError):
            msg = str(exc).lower()
            if "context" in msg or "too long" in msg or "maximum" in msg:
                return ContextWindowExceededError(
                    "The request was too large for this model's context window. "
                    "Try a shorter topic.",
                    technical_detail=str(exc),
                )
            return UnsupportedModelError(
                "Groq rejected the request as invalid.",
                technical_detail=str(exc),
            )
        if isinstance(exc, (groq.APIConnectionError, groq.APITimeoutError)):
            return ProviderUnavailableError(
                "Groq is temporarily unreachable. Please try again.",
                technical_detail=str(exc),
            )
        if isinstance(exc, groq.APIStatusError) and exc.status_code >= 500:
            return ProviderUnavailableError(
                "Groq returned a temporary server error. Please try again.",
                technical_detail=str(exc),
            )
        return BlogForgeLLMError(
            "Groq returned an unexpected error.",
            technical_detail=str(exc),
        )


def _retry_after_seconds(exc: Exception):
    try:
        header = exc.response.headers.get("retry-after")
        return float(header) if header is not None else None
    except Exception:
        return None
