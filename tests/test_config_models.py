from config.models import MODEL_REGISTRY, get_model_info, list_models, list_providers


def test_registry_entries_have_unique_provider_model_pairs():
    pairs = [(m.provider, m.model_id) for m in MODEL_REGISTRY]
    assert len(pairs) == len(set(pairs))


def test_registry_entries_have_required_fields():
    for m in MODEL_REGISTRY:
        assert m.provider
        assert m.model_id
        assert m.display_name
        assert m.tier in ("free", "paid")
        assert m.max_output_tokens > 0
        assert m.structured_output_method in ("json_schema", "function_calling")


def test_list_providers_matches_registry():
    providers = list_providers()
    assert set(providers) == {m.provider for m in MODEL_REGISTRY}
    assert len(providers) == len(set(providers))


def test_list_models_filters_by_provider_and_tier():
    groq_models = list_models(provider="groq")
    assert groq_models
    assert all(m.provider == "groq" for m in groq_models)

    free_models = list_models(tier="free")
    assert free_models
    assert all(m.tier == "free" for m in free_models)


def test_get_model_info_found_and_missing():
    info = get_model_info("anthropic", "claude-sonnet-5")
    assert info.provider == "anthropic"

    try:
        get_model_info("anthropic", "does-not-exist")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown model")


def test_groq_is_the_only_free_provider():
    # Locks in the intentional design choice: Groq is BlogForge's free tier.
    free_providers = {m.provider for m in MODEL_REGISTRY if m.tier == "free"}
    assert free_providers == {"groq"}
