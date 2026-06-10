"""Shared graph state (assignment requirement 1: TypedDict + reducer).

`research_results` uses an `operator.add` reducer so every research sub-query
appends its snippets to the list instead of overwriting it. All other keys use
the default last-write-wins behaviour.

Structured outputs (research/outline/draft/seo) are stored as plain dicts
(`model.model_dump()`) so the state stays JSON-serializable for the MemorySaver
checkpoint and the Streamlit JSON download.
"""
import operator
from typing import TypedDict, List, Annotated


class BlogState(TypedDict, total=False):
    topic: str
    research_results: Annotated[List[str], operator.add]  # append reducer
    research: dict          # ResearchOutput.model_dump()
    outline: dict           # OutlineOutput.model_dump()
    draft: dict             # DraftOutput.model_dump()
    seo_output: dict        # SEOOutput.model_dump()
    quality_score: int
    quality_feedback: str
    revision_count: int
    human_feedback: str
    review_action: str      # "approve" | "edit" (set by human_review_node)
    status: str             # human-readable stage label for the UI
    thread_id: str
    final_markdown: str     # published post (set by publish_node)
    final_json: str         # full state snapshot as JSON (set by publish_node)
