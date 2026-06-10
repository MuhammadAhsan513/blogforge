"""The seven BlogForge nodes (assignment requirement 2: meaningful nodes).

Pipeline: research -> outline -> draft -> seo -> quality_check -> human_review -> publish
Each node reads the shared BlogState, does real LLM/tool work, and returns a
partial state update. Structured outputs are produced via
`llm.with_structured_output(Model)` (requirement 7) and stored as dicts.
"""
import json
import os
import re
import time
from datetime import datetime, timezone

from groq import RateLimitError
from langgraph.types import interrupt
from langchain_core.output_parsers import PydanticOutputParser

from llm import get_llm


def _retry_after_seconds(exc) -> float | None:
    """Parse 'try again in 1m23.4s' from a Groq rate-limit error message."""
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(exc))
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + float(m.group(2) or 0)
from models import ResearchOutput, OutlineOutput, DraftOutput, SEOOutput, QualityOutput
from tools import web_search_tool, seo_scorer_tool
from prompts import (
    research_prompt, outline_prompt, draft_prompt, seo_prompt, quality_prompt,
)


def _structured(model_cls, messages, api_key=None):
    """Call the LLM with structured output, returning a Pydantic instance.

    Robust across models: larger models (e.g. llama-3.3-70b) handle the default
    `function_calling` method well, while smaller ones (e.g. llama-3.1-8b-instant)
    are far more reliable with `json_mode`. We pick the likely-best method per
    model and fall back to the other if it fails (`tool_use_failed`, etc.).
    Both paths use `with_structured_output()` (assignment requirement 7).
    """
    llm = get_llm(api_key=api_key)
    model_name = os.getenv("GROQ_MODEL", "")
    prefer_json = "instant" in model_name or "8b" in model_name
    schema = json.dumps(model_cls.model_json_schema())

    def via_json():
        msgs = list(messages) + [
            ("system", f"Return ONLY a single JSON object matching this schema, "
                       f"with no extra text or markdown: {schema}")
        ]
        return llm.with_structured_output(model_cls, method="json_mode").invoke(msgs)

    def via_tools():
        return llm.with_structured_output(model_cls).invoke(messages)

    def via_manual():
        # Last resort: plain completion + PydanticOutputParser. Its format
        # instructions tell the model to emit an *instance* (not the schema),
        # and .parse() tolerantly extracts JSON from surrounding text/fences.
        parser = PydanticOutputParser(pydantic_object=model_cls)
        msgs = list(messages) + [("system", parser.get_format_instructions())]
        raw = llm.invoke(msgs).content
        try:
            return parser.parse(raw)
        except Exception:
            # extra-tolerant: grab the first valid JSON object from the text
            start = raw.find("{")
            obj, _ = json.JSONDecoder().raw_decode(raw[start:])
            return model_cls(**obj)

    order = [via_json, via_tools, via_manual] if prefer_json else [via_tools, via_json, via_manual]

    def call_once():
        last_err = None
        for attempt in order:
            try:
                res = attempt()
                return model_cls(**res) if isinstance(res, dict) else res
            except RateLimitError:
                raise  # don't waste the other strategies on a rate limit
            except Exception as exc:  # format failure — try the next strategy
                last_err = exc
        raise last_err

    # One short wait-and-retry for per-minute (TPM) limits, which clear quickly.
    # Long per-day (TPD) limits are re-raised immediately for the UI to surface.
    for round_idx in range(2):
        try:
            return call_once()
        except RateLimitError as exc:
            wait = _retry_after_seconds(exc)
            if round_idx == 0 and wait is not None and wait <= 25:
                time.sleep(wait + 1)
                continue
            raise


# --------------------------------------------------------------------------- #
# 1. Research — uses the DuckDuckGo tool, appends to research_results (reducer)
# --------------------------------------------------------------------------- #
def research_node(state, config=None):
    topic = state["topic"]
    api_key = (config or {}).get("configurable", {}).get("api_key")

    # Multi-angle search; each call goes through the LangChain tool (tool use).
    queries = [topic, f"{topic} tips and benefits"]
    raw_snippets = []
    for q in queries:
        result = web_search_tool.invoke({"query": q})
        if result and "No results" not in result:
            raw_snippets.extend(result.split("\n"))
    # Trim to keep the research context (and token usage) small.
    raw_snippets = [s[:240] for s in raw_snippets if s.strip()][:8]

    research = _structured(ResearchOutput, research_prompt(topic, raw_snippets), api_key)
    return {
        "research_results": raw_snippets or [f"(no web results for '{topic}')"],
        "research": research.model_dump(),
        "status": "researched",
    }


# --------------------------------------------------------------------------- #
# 2. Outline
# --------------------------------------------------------------------------- #
def outline_node(state, config=None):
    api_key = (config or {}).get("configurable", {}).get("api_key")
    outline = _structured(
        OutlineOutput, outline_prompt(state["topic"], state.get("research", {})), api_key
    )
    return {"outline": outline.model_dump(), "status": "outlined"}


# --------------------------------------------------------------------------- #
# 3. Draft — increments revision_count; consumes feedback on retries (loop)
# --------------------------------------------------------------------------- #
def draft_node(state, config=None):
    api_key = (config or {}).get("configurable", {}).get("api_key")
    draft = _structured(
        DraftOutput,
        draft_prompt(
            state["topic"],
            state.get("research", {}),
            state.get("outline", {}),
            quality_feedback=state.get("quality_feedback", ""),
            human_feedback=state.get("human_feedback", ""),
        ),
        api_key,
    )
    return {
        "draft": draft.model_dump(),
        "revision_count": state.get("revision_count", 0) + 1,
        "human_feedback": "",   # consumed; clear so it isn't reused
        "status": "drafted",
    }


# --------------------------------------------------------------------------- #
# 4. SEO — structured output + custom SEO scorer tool
# --------------------------------------------------------------------------- #
def seo_node(state, config=None):
    api_key = (config or {}).get("configurable", {}).get("api_key")
    draft = state.get("draft", {})
    seo = _structured(SEOOutput, seo_prompt(state["topic"], draft), api_key)

    # Run the custom SEO scorer tool over the draft body.
    body = "\n\n".join(draft.get("sections", []))
    report = seo_scorer_tool.invoke({"text": body, "keywords": seo.keywords})

    seo_dict = seo.model_dump()
    seo_dict["report"] = report
    return {"seo_output": seo_dict, "status": "seo_optimized"}


# --------------------------------------------------------------------------- #
# 5. Quality check — self-evaluation that drives the conditional retry loop
# --------------------------------------------------------------------------- #
def quality_check_node(state, config=None):
    api_key = (config or {}).get("configurable", {}).get("api_key")
    seo_report = state.get("seo_output", {}).get("report", {})
    quality = _structured(
        QualityOutput, quality_prompt(state["topic"], state.get("draft", {}), seo_report), api_key
    )
    return {
        "quality_score": quality.score,
        "quality_feedback": quality.feedback,
        "status": "quality_checked",
    }


# --------------------------------------------------------------------------- #
# 6. Human review — pauses the graph via interrupt() for approve/edit
# --------------------------------------------------------------------------- #
def human_review_node(state, config=None):
    decision = interrupt({
        "draft": state.get("draft"),
        "quality_score": state.get("quality_score"),
        "quality_feedback": state.get("quality_feedback"),
        "revision_count": state.get("revision_count"),
    })

    # `decision` is whatever is passed via Command(resume=...)
    if isinstance(decision, dict):
        action = decision.get("action", "approve")
        feedback = decision.get("feedback", "")
    else:
        action = str(decision)
        feedback = ""

    if action == "edit":
        return {"review_action": "edit", "human_feedback": feedback, "status": "editing"}
    return {"review_action": "approve", "human_feedback": "", "status": "approved"}


# --------------------------------------------------------------------------- #
# 7. Publish — formats final markdown + JSON snapshot
# --------------------------------------------------------------------------- #
def publish_node(state, config=None):
    draft = state.get("draft", {})
    seo = state.get("seo_output", {})
    body = "\n\n".join(draft.get("sections", []))

    keywords = ", ".join(seo.get("keywords", []))
    markdown = (
        f"# {draft.get('title', state['topic'])}\n\n"
        f"> {seo.get('meta_description', '')}\n\n"
        f"{body}\n\n"
        f"---\n"
        f"**Keywords:** {keywords}\n\n"
        f"**Slug:** `{seo.get('slug', '')}`\n"
    )

    snapshot = {
        "topic": state.get("topic"),
        "title": draft.get("title"),
        "draft": draft,
        "seo": {k: v for k, v in seo.items() if k != "report"},
        "seo_report": seo.get("report", {}),
        "quality_score": state.get("quality_score"),
        "revision_count": state.get("revision_count"),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "status": "published",
        "final_markdown": markdown,
        "final_json": json.dumps(snapshot, indent=2, ensure_ascii=False),
    }
