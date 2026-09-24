"""The seven BlogForge nodes (assignment requirement 2: meaningful nodes).

Pipeline: research -> outline -> draft -> seo -> quality_check -> human_review -> publish

Each node reads the shared BlogState, does real LLM/tool work, and returns a
partial state update. Structured outputs are produced via
`llm.invoke_structured(Model, ...)` (requirement 7) and stored as dicts.

The LLM backend is provider-agnostic: which provider/model handles each
call is resolved per-run from `config["configurable"]` (see `_run_context`
below) and dispatched through `llm.py` / `providers/`. Nodes never import
a provider SDK directly.
"""

import json
from datetime import datetime, timezone

from langgraph.types import interrupt

from llm import invoke_structured

from config.models import get_model_info
from config.plans import get_plan_config

from models import (
    ResearchOutput,
    OutlineOutput,
    DraftOutput,
    SEOOutput,
    QualityOutput,
)

from tools import web_search_tool, seo_scorer_tool

from prompts import (
    research_prompt,
    outline_prompt,
    draft_prompt,
    seo_prompt,
    quality_prompt,
)

# Fallback provider/model for callers that invoke the graph without a
# Streamlit-populated config (e.g. the notebook, or direct graph.invoke()).
_DEFAULT_PROVIDER = "anthropic"
_DEFAULT_MODEL = "claude-sonnet-5"


# --------------------------------------------------------------------------- #
# LLM run context + structured-output helper
# --------------------------------------------------------------------------- #
def _run_context(config):
    """Resolve (provider, model, api_key, plan_tier) from the run config.

    provider/model/api_key come from `config["configurable"]`, populated by
    the Streamlit sidebar (see app.py). Nodes never know which provider is
    actually handling the call — that's entirely decided here and in llm.py.
    """
    cfg = (config or {}).get("configurable", {})
    provider = cfg.get("provider") or _DEFAULT_PROVIDER
    model = cfg.get("model") or _DEFAULT_MODEL
    api_key = cfg.get("api_key")

    tier = cfg.get("plan")
    if not tier:
        try:
            tier = get_model_info(provider, model).tier
        except ValueError:
            tier = "paid"

    return provider, model, api_key, tier


def _structured(model_cls, messages, ctx, stage):
    """Call the active LLM with structured output and return a Pydantic instance.

    `stage` selects this call's token budget from the active plan
    (config/plans.py) so small tasks (outline, seo) don't consume the same
    completion-token budget as the draft stage.
    """
    provider, model, api_key, tier = ctx
    plan = get_plan_config(tier)

    return invoke_structured(
        model_cls,
        messages,
        provider=provider,
        model=model,
        api_key=api_key,
        max_tokens=plan.token_budgets[stage],
        max_retries=plan.max_retries,
    )


# --------------------------------------------------------------------------- #
# 1. Research — uses the DuckDuckGo tool
# --------------------------------------------------------------------------- #
def research_node(state, config=None):
    """Research the topic using web search and the active LLM."""

    topic = state["topic"]

    ctx = _run_context(config)
    limits = get_plan_config(ctx[3]).research

    # Multi-angle search, capped by the active plan's query budget.
    queries = [
        topic,
        f"{topic} tips and benefits",
    ][: limits.queries]

    raw_snippets = []

    for q in queries:
        result = web_search_tool.invoke({"query": q, "max_results": limits.results_per_query})

        if result and "No results" not in result:
            raw_snippets.extend(result.split("\n"))

    # Keep research context small to reduce token usage.
    raw_snippets = [
        s[: limits.snippet_chars]
        for s in raw_snippets
        if s.strip()
    ][: limits.max_snippets]

    research = _structured(
        ResearchOutput,
        research_prompt(topic, raw_snippets),
        ctx,
        "research",
    )

    return {
        "research_results": raw_snippets
        or [f"(no web results for '{topic}')"],

        "research": research.model_dump(),

        "status": "researched",
    }


# --------------------------------------------------------------------------- #
# 2. Outline
# --------------------------------------------------------------------------- #
def outline_node(state, config=None):
    """Generate the blog outline using the active LLM."""

    ctx = _run_context(config)

    outline = _structured(
        OutlineOutput,
        outline_prompt(
            state["topic"],
            state.get("research", {}),
        ),
        ctx,
        "outline",
    )

    return {
        "outline": outline.model_dump(),
        "status": "outlined",
    }


# --------------------------------------------------------------------------- #
# 3. Draft — increments revision_count; consumes feedback on retries
# --------------------------------------------------------------------------- #
def draft_node(state, config=None):
    """Generate or revise the full blog draft."""

    ctx = _run_context(config)

    draft = _structured(
        DraftOutput,
        draft_prompt(
            state["topic"],
            state.get("research", {}),
            state.get("outline", {}),
            quality_feedback=state.get("quality_feedback", ""),
            human_feedback=state.get("human_feedback", ""),
        ),
        ctx,
        "draft",
    )

    return {
        "draft": draft.model_dump(),

        "revision_count": state.get("revision_count", 0) + 1,

        # Feedback has now been consumed.
        "human_feedback": "",

        "status": "drafted",
    }


# --------------------------------------------------------------------------- #
# 4. SEO — structured output + custom SEO scorer
# --------------------------------------------------------------------------- #
def seo_node(state, config=None):
    """Generate SEO metadata and run the custom SEO scorer."""

    ctx = _run_context(config)
    truncation = get_plan_config(ctx[3]).draft_truncation

    draft = state.get("draft", {})

    seo = _structured(
        SEOOutput,
        seo_prompt(
            state["topic"],
            draft,
            max_body_chars=truncation.seo_chars,
        ),
        ctx,
        "seo",
    )

    # Run the custom SEO scorer over the generated draft.
    body = "\n\n".join(
        draft.get("sections", [])
    )

    report = seo_scorer_tool.invoke(
        {
            "text": body,
            "keywords": seo.keywords,
        }
    )

    seo_dict = seo.model_dump()

    seo_dict["report"] = report

    return {
        "seo_output": seo_dict,
        "status": "seo_optimized",
    }


# --------------------------------------------------------------------------- #
# 5. Quality check — self-evaluation that drives conditional retry loop
# --------------------------------------------------------------------------- #
def quality_check_node(state, config=None):
    """Evaluate the draft quality using the active LLM."""

    ctx = _run_context(config)
    truncation = get_plan_config(ctx[3]).draft_truncation

    seo_report = state.get(
        "seo_output",
        {},
    ).get(
        "report",
        {},
    )

    quality = _structured(
        QualityOutput,
        quality_prompt(
            state["topic"],
            state.get("draft", {}),
            seo_report,
            max_body_chars=truncation.quality_chars,
        ),
        ctx,
        "quality",
    )

    return {
        "quality_score": quality.score,

        "quality_feedback": quality.feedback,

        "status": "quality_checked",
    }


# --------------------------------------------------------------------------- #
# 6. Human review — pauses the graph via interrupt()
# --------------------------------------------------------------------------- #
def human_review_node(state, config=None):
    """Pause the graph and wait for human approval or editing instructions."""

    decision = interrupt(
        {
            "draft": state.get("draft"),

            "quality_score": state.get("quality_score"),

            "quality_feedback": state.get("quality_feedback"),

            "revision_count": state.get("revision_count"),
        }
    )

    # `decision` is whatever is passed via Command(resume=...).
    if isinstance(decision, dict):

        action = decision.get(
            "action",
            "approve",
        )

        feedback = decision.get(
            "feedback",
            "",
        )

    else:

        action = str(decision)

        feedback = ""

    if action == "edit":

        return {
            "review_action": "edit",

            "human_feedback": feedback,

            "status": "editing",
        }

    return {
        "review_action": "approve",

        "human_feedback": "",

        "status": "approved",
    }


# --------------------------------------------------------------------------- #
# 7. Publish — formats final markdown + JSON snapshot
# --------------------------------------------------------------------------- #
def publish_node(state, config=None):
    """Create the final Markdown article and JSON snapshot."""

    draft = state.get(
        "draft",
        {},
    )

    seo = state.get(
        "seo_output",
        {},
    )

    body = "\n\n".join(
        draft.get(
            "sections",
            [],
        )
    )

    keywords = ", ".join(
        seo.get(
            "keywords",
            [],
        )
    )

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

        "seo": {
            k: v
            for k, v in seo.items()
            if k != "report"
        },

        "seo_report": seo.get(
            "report",
            {},
        ),

        "quality_score": state.get(
            "quality_score"
        ),

        "revision_count": state.get(
            "revision_count"
        ),

        "published_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    return {
        "status": "published",

        "final_markdown": markdown,

        "final_json": json.dumps(
            snapshot,
            indent=2,
            ensure_ascii=False,
        ),
    }