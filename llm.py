"""Provider-agnostic LLM facade for BlogForge.

`nodes.py` never imports a provider SDK or a LangChain chat-model class
directly — it only calls `invoke_structured()` below. Which provider
actually handles the call is decided entirely by the `provider`/`model`
arguments (sourced from `config["configurable"]`, ultimately from the
Streamlit sidebar). Swapping providers, adding a new one, or changing
retry/error behavior never requires touching `nodes.py` or `graph.py`.
"""

import logging
import time
from typing import List, Optional, Tuple, Type, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from providers import get_provider_adapter
from providers.errors import BlogForgeLLMError, MissingAPIKeyError

logger = logging.getLogger("blogforge")

_RETRY_BACKOFF_SECONDS = 1.5
_RETRY_BACKOFF_CAP_SECONDS = 8.0

ModelT = TypeVar("ModelT", bound=BaseModel)


def get_llm(provider: str, model: str, api_key: Optional[str], max_tokens: int) -> BaseChatModel:
    """Return a configured LangChain chat model for the given provider/model.

    Raises MissingAPIKeyError if no API key was supplied.
    """
    key = (api_key or "").strip()
    if not key:
        raise MissingAPIKeyError(
            f"No API key was provided for {provider}. Enter one in the Streamlit sidebar."
        )

    adapter = get_provider_adapter(provider)
    return adapter.build_chat_model(model_id=model, api_key=key, max_tokens=max_tokens)


def invoke_structured(
    model_cls: Type[ModelT],
    messages: List[Tuple[str, str]],
    *,
    provider: str,
    model: str,
    api_key: Optional[str],
    max_tokens: int,
    max_retries: int = 1,
) -> ModelT:
    """Call the selected LLM with structured output and return a validated instance.

    Retries are bounded by `max_retries` and only happen for retryable
    normalized errors (rate limits, transient provider failures); every
    other error is raised immediately. A provider's retry-after hint is
    respected (capped) when present.
    """
    adapter = get_provider_adapter(provider)
    llm = get_llm(provider=provider, model=model, api_key=api_key, max_tokens=max_tokens)
    structured_llm = llm.with_structured_output(
        model_cls, method=adapter.structured_output_method(model)
    )

    attempt = 0
    while True:
        try:
            result = structured_llm.invoke(messages)
            if isinstance(result, dict):
                return model_cls(**result)
            return result
        except BlogForgeLLMError:
            raise
        except Exception as exc:
            normalized = adapter.normalize_error(exc)
            logger.error(
                "LLM call failed (provider=%s model=%s attempt=%d): %s",
                provider,
                model,
                attempt + 1,
                normalized.technical_detail,
            )
            attempt += 1
            if not normalized.retryable or attempt > max_retries:
                raise normalized from exc
            delay = getattr(normalized, "retry_after", None) or (
                _RETRY_BACKOFF_SECONDS * attempt
            )
            time.sleep(min(delay, _RETRY_BACKOFF_CAP_SECONDS))
