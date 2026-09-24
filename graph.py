"""BlogForge graph assembly.

Workflow type: ITERATIVE + CONDITIONAL.
  * Conditional edges at quality_check (revise vs review) and human_review (publish vs edit).
  * A retry loop draft -> seo -> quality_check -> draft, capped by revision_count.
  * Persistence via MemorySaver + thread_id (requirement 6); interrupt() for human review.
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import BlogState
from nodes import (
    research_node, outline_node, draft_node, seo_node,
    quality_check_node, human_review_node, publish_node,
)

# Fallback tuning knobs, used only when a run doesn't set plan-derived
# state fields (e.g. direct graph.invoke() calls outside app.py, such as
# the notebook). app.py normally seeds "quality_threshold"/"max_drafts"
# from the active plan (see config/plans.py) into the initial state.
QUALITY_THRESHOLD = 75   # minimum acceptable quality score
MAX_DRAFTS = 2           # initial draft + 1 retry


def route_after_quality(state) -> str:
    """Conditional edge: loop back to draft on low quality, else go to human review."""
    score = state.get("quality_score", 0)
    revisions = state.get("revision_count", 0)
    threshold = state.get("quality_threshold", QUALITY_THRESHOLD)
    max_drafts = state.get("max_drafts", MAX_DRAFTS)
    if score < threshold and revisions < max_drafts:
        return "revise"
    return "review"


def route_after_review(state) -> str:
    """Conditional edge: human approved -> publish; requested edits -> redraft."""
    return "publish" if state.get("review_action") == "approve" else "revise"


def build_graph(checkpointer=None):
    """Construct and compile the BlogForge StateGraph."""
    workflow = StateGraph(BlogState)

    workflow.add_node("research", research_node)
    workflow.add_node("outline", outline_node)
    workflow.add_node("draft", draft_node)
    workflow.add_node("seo", seo_node)
    workflow.add_node("quality_check", quality_check_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("publish", publish_node)

    # Sequential backbone
    workflow.add_edge(START, "research")
    workflow.add_edge("research", "outline")
    workflow.add_edge("outline", "draft")
    workflow.add_edge("draft", "seo")
    workflow.add_edge("seo", "quality_check")

    # Conditional branch + retry loop after quality check
    workflow.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {"revise": "draft", "review": "human_review"},
    )

    # Conditional branch after human review
    workflow.add_conditional_edges(
        "human_review",
        route_after_review,
        {"publish": "publish", "revise": "draft"},
    )

    workflow.add_edge("publish", END)

    return workflow.compile(checkpointer=checkpointer or MemorySaver())


# Convenience singleton for quick imports/notebook use.
graph = build_graph()
