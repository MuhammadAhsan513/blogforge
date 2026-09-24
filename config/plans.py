"""Usage-tier plans: FREE vs PAID budgets for the BlogForge workflow.

A model's `tier` (see `config/models.py`) selects a plan here. The plan
controls per-stage token budgets, how much research context is kept,
how many draft/revision cycles are allowed, and how many times a
failed LLM call may be retried. Nothing else in the codebase should
hardcode these numbers — `nodes.py` and `graph.py` read them from here
so a new tier (or a change to an existing one) only requires editing
this file.

Paid-tier values intentionally match BlogForge's original hardcoded
behavior exactly, so switching to a paid provider does not change
output quality. Free-tier values are deliberately tighter to keep a
free-tier account's token/request usage low while still producing a
usable post.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ResearchLimits:
    queries: int
    results_per_query: int
    snippet_chars: int
    max_snippets: int


@dataclass(frozen=True)
class DraftTruncation:
    seo_chars: int
    quality_chars: int


@dataclass(frozen=True)
class PlanConfig:
    tier: str
    token_budgets: Dict[str, int]  # stage -> max_tokens
    research: ResearchLimits
    draft_truncation: DraftTruncation
    max_drafts: int
    quality_threshold: int
    max_retries: int


PLAN_CONFIGS: Dict[str, PlanConfig] = {
    "paid": PlanConfig(
        tier="paid",
        token_budgets={
            "research": 1200,
            "outline": 800,
            "draft": 4096,
            "seo": 800,
            "quality": 1000,
        },
        research=ResearchLimits(
            queries=2,
            results_per_query=4,
            snippet_chars=240,
            max_snippets=8,
        ),
        draft_truncation=DraftTruncation(seo_chars=1800, quality_chars=2200),
        max_drafts=2,
        quality_threshold=75,
        max_retries=2,
    ),
    "free": PlanConfig(
        tier="free",
        token_budgets={
            "research": 700,
            "outline": 500,
            "draft": 1800,
            "seo": 500,
            "quality": 600,
        },
        research=ResearchLimits(
            queries=1,
            results_per_query=4,
            snippet_chars=160,
            max_snippets=4,
        ),
        draft_truncation=DraftTruncation(seo_chars=1000, quality_chars=1400),
        max_drafts=1,
        quality_threshold=75,
        max_retries=1,
    ),
}

DEFAULT_TIER = "free"


def get_plan_config(tier: str) -> PlanConfig:
    """Return the PlanConfig for a tier, falling back to the default tier."""
    return PLAN_CONFIGS.get(tier, PLAN_CONFIGS[DEFAULT_TIER])
