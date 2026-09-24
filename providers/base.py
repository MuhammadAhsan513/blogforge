"""Provider adapter interface.

Every provider (Anthropic, OpenAI, Groq, or a future one) implements
this interface. `llm.py` is the only caller — it never imports a
provider SDK or LangChain chat-model class directly, so adding a new
provider never requires touching `llm.py`, `nodes.py`, or `graph.py`.
"""

from abc import ABC, abstractmethod

from langchain_core.language_models.chat_models import BaseChatModel

from providers.errors import BlogForgeLLMError


class ProviderAdapter(ABC):
    """Common interface every provider adapter must implement."""

    #: Human-readable provider name, e.g. "Anthropic".
    display_name: str = "Provider"

    @abstractmethod
    def build_chat_model(self, model_id: str, api_key: str, max_tokens: int) -> BaseChatModel:
        """Construct a LangChain chat model for this provider."""

    @abstractmethod
    def structured_output_method(self, model_id: str) -> str:
        """Return the `with_structured_output(method=...)` value for this model."""

    @abstractmethod
    def normalize_error(self, exc: Exception) -> BlogForgeLLMError:
        """Map a raw SDK exception to a normalized BlogForgeLLMError."""
