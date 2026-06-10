"""LLM factory for BlogForge.

Uses Groq (https://console.groq.com) via langchain-groq. The default model
`llama-3.3-70b-versatile` supports tool-calling, which `with_structured_output()`
relies on for reliable Pydantic parsing.
"""
import os
from langchain_groq import ChatGroq

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
# Lighter/faster fallback if the 70B model hits free-tier rate limits.
FALLBACK_MODEL = "llama-3.1-8b-instant"


def get_llm(api_key: str | None = None, model: str | None = None, temperature: float = 0.4) -> ChatGroq:
    """Return a configured ChatGroq client.

    The key can come from (in order): the explicit `api_key` arg, or the
    GROQ_API_KEY environment variable (loaded from `.env`).

    The model is resolved at call time from: the explicit `model` arg, the
    GROQ_MODEL env var (which the Streamlit sidebar sets when you pick a model),
    then the default.

    `max_retries=0`: on a 429 rate-limit Groq returns Retry-After of several
    minutes; the default client would silently sleep and retry, making the app
    look frozen. We fail fast so the UI can show a clear message instead.
    """
    key = (api_key or os.getenv("GROQ_API_KEY") or "").strip()
    if not key:
        raise ValueError(
            "No Groq API key found. Set GROQ_API_KEY in your .env file "
            "(copy .env.example) or paste it in the Streamlit sidebar."
        )
    # ChatGroq reads GROQ_API_KEY from the environment; set it so we don't
    # depend on constructor alias differences across langchain-groq versions.
    os.environ["GROQ_API_KEY"] = key
    model = model or os.getenv("GROQ_MODEL") or DEFAULT_MODEL
    return ChatGroq(
        model=model,
        temperature=temperature,
        max_retries=0,
    )
