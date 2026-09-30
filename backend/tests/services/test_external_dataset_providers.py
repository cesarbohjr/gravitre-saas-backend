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


def test_huggingface_locator_rejects_urls_and_credentials_before_network():
    provider = get_external_dataset_provider("huggingface")
    for locator in (
        "https://huggingface.co/datasets/org/example",
        "org/example?token=secret",
        "org/example#fragment",
        "org/example?api_key=secret",
    ):
        try:
            provider.inspect(locator)
        except ValueError as exc:
            assert "repository id" in str(exc)
        else:
            raise AssertionError(f"expected unsafe locator refusal: {locator}")


def test_kaggle_is_registered_as_free_reference_provider():
    providers = list_external_dataset_providers()
    kaggle = next(row for row in providers if row["id"] == "kaggle")
    assert kaggle["capabilities"] == ("search", "inspect", "reference")
    assert kaggle["materialization"] == "explicit_only"
    assert "free" in kaggle["notes"].lower()


def test_kaggle_locator_requires_owner_dataset_handle():
    provider = get_external_dataset_provider("kaggle")
    for locator in (
        "https://www.kaggle.com/datasets/owner/example",
        "owner/example?token=secret",
        "example-without-owner",
        "owner/example/extra",
    ):
        try:
            provider.inspect(locator)
        except ValueError as exc:
            assert "owner/dataset" in str(exc)
        else:
            raise AssertionError(f"expected unsafe Kaggle locator refusal: {locator}")
