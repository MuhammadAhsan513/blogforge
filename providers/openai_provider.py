"""OpenAI provider adapter."""

from langchain_openai import ChatOpenAI

from providers.base import ProviderAdapter
from providers.errors import (
    BlogForgeLLMError,
    ContextWindowExceededError,
    InvalidAPIKeyError,
    ProviderUnavailableError,
    RateLimitExceededError,
    UnsupportedModelError,
)


class OpenAIAdapter(ProviderAdapter):
    display_name = "OpenAI"

    def build_chat_model(self, model_id: str, api_key: str, max_tokens: int) -> ChatOpenAI:
        return ChatOpenAI(
            model=model_id,
            api_key=api_key,
            max_tokens=max_tokens,
            max_retries=0,  # BlogForge does its own bounded retries in llm.py
        )

    def structured_output_method(self, model_id: str) -> str:
        # "function_calling" is the broadly compatible default across GPT-4o
        # snapshots. Flip a registry entry's structured_output_method to
        # "json_schema" for models confirmed to support OpenAI Structured
        # Outputs in strict mode.
        return "function_calling"

    def normalize_error(self, exc: Exception) -> BlogForgeLLMError:
        import openai

        if isinstance(exc, openai.AuthenticationError):
            return InvalidAPIKeyError(
                "OpenAI rejected the API key. Double-check the key in the sidebar.",
                technical_detail=str(exc),
            )
        if isinstance(exc, openai.RateLimitError):
            return RateLimitExceededError(
                "OpenAI's rate limit was hit for this key. Wait a moment and try again, "
                "or switch to a different provider/model in the sidebar.",
                retry_after=_retry_after_seconds(exc),
                technical_detail=str(exc),
            )
        if isinstance(exc, openai.NotFoundError):
            return UnsupportedModelError(
                "The selected OpenAI model is not available for this API key.",
                technical_detail=str(exc),
            )
        if isinstance(exc, openai.BadRequestError):
            msg = str(exc).lower()
            if "context" in msg or "too long" in msg or "maximum context" in msg:
                return ContextWindowExceededError(
                    "The request was too large for this model's context window. "
                    "Try a shorter topic or switch to a model with a larger context window.",
                    technical_detail=str(exc),
                )
            return UnsupportedModelError(
                "OpenAI rejected the request as invalid.",
                technical_detail=str(exc),
            )
        if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
            return ProviderUnavailableError(
                "OpenAI is temporarily unreachable. Please try again.",
                technical_detail=str(exc),
            )
        if isinstance(exc, openai.APIStatusError) and exc.status_code >= 500:
            return ProviderUnavailableError(
                "OpenAI returned a temporary server error. Please try again.",
                technical_detail=str(exc),
            )
        return BlogForgeLLMError(
            "OpenAI returned an unexpected error.",
            technical_detail=str(exc),
        )


def _retry_after_seconds(exc: Exception):
    try:
        header = exc.response.headers.get("retry-after")
        return float(header) if header is not None else None
    except Exception:
        return None
