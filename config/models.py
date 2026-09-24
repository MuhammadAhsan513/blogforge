"""Provider/model registry.

This is the single source of truth for which providers and models
BlogForge supports. The Streamlit UI, the LLM factory, and the plan
layer all read from this registry instead of hardcoding provider or
model logic. Adding a new model (or even a new provider) only requires
adding entries here plus a provider adapter in `providers/` — nothing
in `nodes.py` or `graph.py` needs to change.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ModelInfo:
    """Metadata describing one selectable (provider, model) pair."""

    provider: str  # "anthropic" | "openai" | "groq"
    model_id: str  # the literal model ID the provider's API expects
    display_name: str
    tier: str  # "free" | "paid" — drives which plan budgets apply
    max_output_tokens: int  # provider/model ceiling for completion tokens
    structured_output_method: str  # "json_schema" | "function_calling"
    notes: str = ""


MODEL_REGISTRY: List[ModelInfo] = [
    # --- Anthropic (paid, bring-your-own-key) ---------------------------
    ModelInfo(
        provider="anthropic",
        model_id="claude-sonnet-5",
        display_name="Claude Sonnet 5",
        tier="paid",
        max_output_tokens=8192,
        structured_output_method="json_schema",
        notes="Recommended default. Highest quality drafts.",
    ),
    ModelInfo(
        provider="anthropic",
        model_id="claude-haiku-4-5-20251001",
        display_name="Claude Haiku 4.5",
        tier="paid",
        max_output_tokens=8192,
        structured_output_method="json_schema",
        notes="Faster and cheaper than Sonnet 5, still Anthropic quality.",
    ),
    # --- OpenAI (paid, bring-your-own-key) -------------------------------
    ModelInfo(
        provider="openai",
        model_id="gpt-4o",
        display_name="GPT-4o",
        tier="paid",
        max_output_tokens=4096,
        structured_output_method="function_calling",
        notes="High quality, broadly compatible structured-output mode.",
    ),
    ModelInfo(
        provider="openai",
        model_id="gpt-4o-mini",
        display_name="GPT-4o mini",
        tier="paid",
        max_output_tokens=4096,
        structured_output_method="function_calling",
        notes="Cheaper/faster OpenAI option.",
    ),
    # --- Groq (free tier, bring-your-own free key) ------------------------
    ModelInfo(
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        display_name="Llama 3.3 70B Versatile (Groq)",
        tier="free",
        max_output_tokens=4096,
        structured_output_method="function_calling",
        notes="Free Groq tier. Best general-purpose free option.",
    ),
    ModelInfo(
        provider="groq",
        model_id="llama-3.1-8b-instant",
        display_name="Llama 3.1 8B Instant (Groq)",
        tier="free",
        max_output_tokens=4096,
        structured_output_method="function_calling",
        notes="Free Groq tier. Lightest/fastest free option; highest daily limit.",
    ),
    ModelInfo(
        provider="groq",
        model_id="openai/gpt-oss-120b",
        display_name="GPT-OSS 120B (Groq)",
        tier="free",
        max_output_tokens=4096,
        structured_output_method="function_calling",
        notes="Free Groq tier.",
    ),
    ModelInfo(
        provider="groq",
        model_id="openai/gpt-oss-20b",
        display_name="GPT-OSS 20B (Groq)",
        tier="free",
        max_output_tokens=4096,
        structured_output_method="function_calling",
        notes="Free Groq tier. Lighter/faster alternative.",
    ),
]


def list_providers() -> List[str]:
    """Return provider names in registry order, without duplicates."""
    seen: List[str] = []
    for entry in MODEL_REGISTRY:
        if entry.provider not in seen:
            seen.append(entry.provider)
    return seen


def list_models(provider: Optional[str] = None, tier: Optional[str] = None) -> List[ModelInfo]:
    """Return registry entries, optionally filtered by provider and/or tier."""
    return [
        m
        for m in MODEL_REGISTRY
        if (provider is None or m.provider == provider) and (tier is None or m.tier == tier)
    ]


def get_model_info(provider: str, model_id: str) -> ModelInfo:
    """Look up a single registry entry. Raises ValueError if unknown."""
    for entry in MODEL_REGISTRY:
        if entry.provider == provider and entry.model_id == model_id:
            return entry
    raise ValueError(f"Unknown model '{model_id}' for provider '{provider}'.")


def default_model_for(provider: str) -> ModelInfo:
    """Return the first (recommended) registry entry for a provider."""
    models = list_models(provider=provider)
    if not models:
        raise ValueError(f"No models registered for provider '{provider}'.")
    return models[0]
