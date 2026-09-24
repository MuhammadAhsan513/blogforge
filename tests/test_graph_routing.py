from graph import MAX_DRAFTS, QUALITY_THRESHOLD, route_after_quality, route_after_review


def test_route_after_quality_uses_module_defaults_when_state_has_no_plan_fields():
    low_score_state = {"quality_score": QUALITY_THRESHOLD - 1, "revision_count": 0}
    assert route_after_quality(low_score_state) == "revise"

    exhausted_state = {"quality_score": QUALITY_THRESHOLD - 1, "revision_count": MAX_DRAFTS}
    assert route_after_quality(exhausted_state) == "review"

    high_score_state = {"quality_score": QUALITY_THRESHOLD, "revision_count": 0}
    assert route_after_quality(high_score_state) == "review"


def test_route_after_quality_honors_plan_derived_state_overrides():
    # Free-tier plan: max_drafts=1, so even a fresh (revision_count=0) low
    # score with a tighter threshold should not loop forever.
    state = {
        "quality_score": 60,
        "revision_count": 1,
        "quality_threshold": 75,
        "max_drafts": 1,
    }
    assert route_after_quality(state) == "review"

    state_within_budget = {
        "quality_score": 60,
        "revision_count": 0,
        "quality_threshold": 75,
        "max_drafts": 1,
    }
    assert route_after_quality(state_within_budget) == "revise"


def test_route_after_review():
    assert route_after_review({"review_action": "approve"}) == "publish"
    assert route_after_review({"review_action": "edit"}) == "revise"
    assert route_after_review({}) == "revise"
