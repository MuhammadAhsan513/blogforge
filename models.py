"""Pydantic v2 models for structured LLM output (assignment requirement 7).

Each blog-production node calls `llm.invoke_structured(Model, ...)` so the LLM
returns typed, validated objects instead of free text. Schemas are kept flat
and well-described because most providers implement structured output via
tool-calling or a JSON-schema mode, both of which work best with simple,
descriptive field shapes (see `providers/*_provider.py` for the per-provider
method choice).
"""
from typing import List
from pydantic import BaseModel, Field


class ResearchOutput(BaseModel):
    """Distilled research about the topic."""
    sources: List[str] = Field(default_factory=list, description="URLs or source titles used")
    key_facts: List[str] = Field(default_factory=list, description="5-8 concrete, citable facts")
    summary: str = Field(description="A 3-5 sentence synthesis of the research")


class OutlineOutput(BaseModel):
    """Structured outline for the blog post."""
    title: str = Field(description="Compelling, specific blog post title")
    sections: List[str] = Field(description="4-7 section headings in logical order")


class DraftOutput(BaseModel):
    """A full blog post draft."""
    title: str = Field(description="Final title of the post")
    sections: List[str] = Field(
        description="One element per section: the full markdown body text for that section, "
                    "starting with a '## Heading' line."
    )
    word_count: int = Field(description="Approximate total word count of the post")


class SEOOutput(BaseModel):
    """SEO metadata for the post."""
    keywords: List[str] = Field(description="6-10 target SEO keywords/phrases")
    meta_description: str = Field(description="<=160 character meta description")
    slug: str = Field(description="URL slug, lowercase words separated by hyphens")


class QualityOutput(BaseModel):
    """Self-evaluation of the draft quality."""
    score: int = Field(description="Overall quality score from 0 to 100", ge=0, le=100)
    feedback: str = Field(description="Specific, actionable feedback for improving the draft")
