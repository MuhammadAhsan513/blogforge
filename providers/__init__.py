"""Provider adapter dispatch.

`get_provider_adapter()` is the only thing outside this package that
should be called. To add a new provider: write a `<name>_provider.py`
module implementing `ProviderAdapter`, register it in `_ADAPTERS`
below, and add its models to `config/models.py`. No other file needs
to change.
"""

from typing import Dict

from providers.anthropic_provider import AnthropicAdapter
from providers.base import ProviderAdapter
from providers.groq_provider import GroqAdapter
from providers.openai_provider import OpenAIAdapter

_ADAPTERS: Dict[str, ProviderAdapter] = {
    "anthropic": AnthropicAdapter(),
    "openai": OpenAIAdapter(),
    "groq": GroqAdapter(),
}


def get_provider_adapter(provider: str) -> ProviderAdapter:
    try:
        return _ADAPTERS[provider]
    except KeyError:
        raise ValueError(f"Unknown provider '{provider}'.") from None
