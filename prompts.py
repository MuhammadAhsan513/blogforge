"""Prompt builders for each BlogForge node.

Each function returns a list of (role, content) message tuples ready to pass to
a `with_structured_output()` runnable. Keeping prompts here keeps nodes.py focused
on graph logic.
"""
from typing import List


def research_prompt(topic: str, raw_snippets: List[str]):
    sources_block = "\n".join(f"- {s}" for s in raw_snippets) or "(no web results — use your own knowledge)"
    return [
        ("system",
         "You are a meticulous research assistant. Distil web search results into "
         "concrete, citable facts. Do not invent sources or URLs."),
        ("human",
         f"Topic: {topic}\n\n"
         f"Web search results:\n{sources_block}\n\n"
         "Extract the key facts and a short synthesis. List the source URLs you "
         "actually used in `sources` (leave empty if none were provided)."),
    ]


def outline_prompt(topic: str, research: dict):
    return [
        ("system",
         "You are an expert content strategist. Produce a clear, logically ordered "
         "blog outline that a writer can follow."),
        ("human",
         f"Topic: {topic}\n\n"
         f"Research summary: {research.get('summary', '')}\n"
         f"Key facts: {research.get('key_facts', [])}\n\n"
         "Create a compelling title and 4-7 section headings."),
    ]


def draft_prompt(topic: str, research: dict, outline: dict,
                 quality_feedback: str = "", human_feedback: str = ""):
    revision_block = ""
    if quality_feedback:
        revision_block += f"\nThe previous draft scored low. Reviewer feedback to address:\n{quality_feedback}\n"
    if human_feedback:
        revision_block += f"\nA human editor requested these changes:\n{human_feedback}\n"

    return [
        ("system",
         "You are a professional blog writer. Write an engaging, well-structured, "
         "factually grounded post in markdown. Each section element must start with "
         "a '## Heading' line followed by 1-2 short paragraphs. Keep the whole post "
         "concise: roughly 500-800 words total (this conserves API tokens)."),
        ("human",
         f"Topic: {topic}\n\n"
         f"Outline title: {outline.get('title', topic)}\n"
         f"Sections to write: {outline.get('sections', [])}\n\n"
         f"Research summary: {research.get('summary', '')}\n"
         f"Key facts to weave in: {research.get('key_facts', [])}\n"
         f"{revision_block}\n"
         "Write the full post, ~500-800 words. Return one `sections` element per outline section."),
    ]


def seo_prompt(topic: str, draft: dict, max_body_chars: int = 1800):
    body = "\n\n".join(draft.get("sections", []))
    return [
        ("system",
         "You are an SEO specialist. Choose high-intent keywords that genuinely "
         "match the content. Keep the meta description under 160 characters."),
        ("human",
         f"Topic: {topic}\n"
         f"Title: {draft.get('title', topic)}\n\n"
         f"Post body:\n{body[:max_body_chars]}\n\n"
         "Produce 6-10 SEO keywords, a meta description, and a URL slug."),
    ]


def quality_prompt(topic: str, draft: dict, seo_report: dict, max_body_chars: int = 2200):
    body = "\n\n".join(draft.get("sections", []))
    return [
        ("system",
         "You are a strict editorial quality reviewer. Score the post 0-100 on "
         "readability, structure, factual depth, and SEO. Be critical: a thin, "
         "generic, or poorly structured post should score below 75."),
        ("human",
         f"Topic: {topic}\n"
         f"Word count: {draft.get('word_count', 'unknown')}\n"
         f"SEO analysis: score={seo_report.get('seo_score')}, "
         f"recommendations={seo_report.get('recommendations')}\n\n"
         f"Post:\n{body[:max_body_chars]}\n\n"
         "Give an overall score and specific, actionable feedback."),
    ]
