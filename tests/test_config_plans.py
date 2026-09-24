from config.plans import PLAN_CONFIGS, get_plan_config


def test_both_tiers_exist():
    assert set(PLAN_CONFIGS) == {"free", "paid"}


def test_get_plan_config_falls_back_to_default_for_unknown_tier():
    fallback = get_plan_config("nonexistent-tier")
    assert fallback.tier == "free"


def test_free_budgets_are_not_more_generous_than_paid():
    free = get_plan_config("free")
    paid = get_plan_config("paid")

    for stage, budget in free.token_budgets.items():
        assert budget <= paid.token_budgets[stage], stage

    assert free.research.queries <= paid.research.queries
    assert free.research.snippet_chars <= paid.research.snippet_chars
    assert free.research.max_snippets <= paid.research.max_snippets
    assert free.max_drafts <= paid.max_drafts
    assert free.max_retries <= paid.max_retries


def test_paid_tier_preserves_original_hardcoded_values():
    # These numbers matched nodes.py/graph.py before the provider-agnostic
    # refactor; paid tier must reproduce them exactly for no behavior change.
    paid = get_plan_config("paid")
    assert paid.token_budgets == {
        "research": 1200,
        "outline": 800,
        "draft": 4096,
        "seo": 800,
        "quality": 1000,
    }
    assert paid.research.queries == 2
    assert paid.research.snippet_chars == 240
    assert paid.research.max_snippets == 8
    assert paid.draft_truncation.seo_chars == 1800
    assert paid.draft_truncation.quality_chars == 2200
    assert paid.max_drafts == 2
    assert paid.quality_threshold == 75


def test_retries_are_bounded_not_unbounded():
    for plan in PLAN_CONFIGS.values():
        assert 0 <= plan.max_retries <= 3
