from app.services.external_dataset_providers import (
    get_external_dataset_provider,
    list_external_dataset_providers,
)


def test_provider_registry_is_provider_neutral_and_huggingface_is_read_only_reference():
    providers = list_external_dataset_providers()
    assert providers
    hf = next(row for row in providers if row["id"] == "huggingface")
    assert hf["capabilities"] == ("search", "inspect", "reference")
    assert hf["materialization"] == "explicit_only"
    assert "automatically downloaded" in hf["notes"]


def test_unknown_dataset_provider_fails_closed():
    try:
        get_external_dataset_provider("unknown-provider")
    except LookupError as exc:
        assert "Unsupported dataset provider" in str(exc)
    else:
        raise AssertionError("expected unsupported provider refusal")
