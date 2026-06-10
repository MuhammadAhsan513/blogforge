"""Tools for BlogForge (assignment requirement 5: tool use).

Two real LangChain tools:
  * web_search_tool  — live DuckDuckGo search (no API key) used by research_node.
  * seo_scorer_tool  — a custom keyword-density analyzer used by seo_node.

Both are exposed as LangChain `@tool` objects so they can be `.invoke()`d from
nodes (and bound to the LLM if desired). The plain helper functions underneath
are kept importable for direct, robust use.
"""
import re
from typing import List
from langchain_core.tools import tool


# --------------------------------------------------------------------------- #
# Web search (DuckDuckGo via the `ddgs` package — no API key required)
# --------------------------------------------------------------------------- #
def run_web_search(query: str, max_results: int = 4) -> List[str]:
    """Return a list of 'title — snippet (url)' strings for a query.

    Degrades gracefully: on any error (rate limit, no network) it returns an
    empty list so the research node can fall back to LLM-only knowledge.
    """
    try:
        from ddgs import DDGS

        results = DDGS().text(query, max_results=max_results)
        snippets = []
        for r in results or []:
            title = (r.get("title") or "").strip()
            body = (r.get("body") or "").strip()
            url = (r.get("href") or r.get("link") or "").strip()
            snippets.append(f"{title} — {body} ({url})")
        return snippets
    except Exception as exc:  # pragma: no cover - network dependent
        return [f"[web search unavailable: {exc}]"]


@tool
def web_search_tool(query: str) -> str:
    """Search the web (DuckDuckGo) for recent, factual information about the query.

    Returns newline-separated result snippets with source URLs.
    """
    snippets = run_web_search(query)
    return "\n".join(snippets) if snippets else "No results found."


# --------------------------------------------------------------------------- #
# Custom SEO scorer (pure Python, no API)
# --------------------------------------------------------------------------- #
def compute_seo(text: str, keywords: List[str]) -> dict:
    """Compute keyword density and a 0-100 SEO score for `text`.

    Heuristic: each target keyword should appear with a density of roughly
    0.5%-2.5% of total words. Score rewards keyword coverage and penalises
    keyword stuffing or absence.
    """
    words = re.findall(r"\b\w+\b", text.lower())
    total = max(len(words), 1)
    text_lower = text.lower()

    densities = {}
    covered = 0
    stuffed = 0
    for kw in keywords:
        kw_l = kw.lower().strip()
        if not kw_l:
            continue
        count = text_lower.count(kw_l)
        density = round(100 * count * max(len(kw_l.split()), 1) / total, 2)
        densities[kw] = density
        if count >= 1:
            covered += 1
        if density > 2.5:
            stuffed += 1

    n = max(len([k for k in keywords if k.strip()]), 1)
    coverage_score = 100 * covered / n          # how many keywords appear at all
    stuffing_penalty = 15 * stuffed
    length_bonus = 10 if total >= 500 else 0     # reward substantial posts
    score = int(max(0, min(100, round(0.85 * coverage_score + length_bonus - stuffing_penalty))))

    recommendations = []
    missing = [k for k in keywords if densities.get(k, 0) == 0]
    if missing:
        recommendations.append(f"Add or increase usage of: {', '.join(missing)}")
    if stuffed:
        recommendations.append("Reduce keyword stuffing (some densities exceed 2.5%).")
    if total < 500:
        recommendations.append("Lengthen the post to at least 500 words for better SEO.")
    if not recommendations:
        recommendations.append("Keyword usage looks balanced.")

    return {
        "word_count": total,
        "keyword_density_pct": densities,
        "seo_score": score,
        "recommendations": recommendations,
    }


@tool
def seo_scorer_tool(text: str, keywords: List[str]) -> dict:
    """Analyse keyword density of `text` against `keywords`.

    Returns word_count, per-keyword density %, a 0-100 seo_score, and
    actionable recommendations.
    """
    return compute_seo(text, keywords)
