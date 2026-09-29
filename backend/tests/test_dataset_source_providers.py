from app.services.dataset_source_providers import (
    DatasetSourceDescriptor,
    DatasetSourcePage,
    clear_dataset_source_providers_for_tests,
    get_dataset_source_provider,
    list_dataset_source_provider_keys,
    register_dataset_source_provider,
)


class _FakeProvider:
    provider_key = "fake"

    def search(self, *, query, cursor=None, limit=20):
        return DatasetSourcePage(
            items=(
                DatasetSourceDescriptor(
                    provider=self.provider_key,
                    external_id="dataset-1",
                    display_name="Dataset 1",
                ),
            ),
            next_cursor=None,
        )

    def describe(self, external_id):
        return DatasetSourceDescriptor(
            provider=self.provider_key,
            external_id=external_id,
            display_name="Dataset 1",
        )

    def sample(self, *, external_id, limit):
        return [{"external_id": external_id, "row": 1}][:limit]


def setup_function():
    clear_dataset_source_providers_for_tests()


def teardown_function():
    clear_dataset_source_providers_for_tests()


def test_provider_registry_is_generic_and_explicit():
    provider = _FakeProvider()
    register_dataset_source_provider(provider)
    assert list_dataset_source_provider_keys() == ["fake"]
    assert get_dataset_source_provider("FAKE") is provider
    page = provider.search(query="dataset")
    assert page.items[0].external_id == "dataset-1"


def test_duplicate_provider_registration_fails():
    provider = _FakeProvider()
    register_dataset_source_provider(provider)
    try:
        register_dataset_source_provider(provider)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("expected duplicate provider registration refusal")


def test_provider_protocol_does_not_own_credentials_or_materialization():
    provider = _FakeProvider()
    descriptor = provider.describe("dataset-1").as_dict()
    assert "credentials" not in descriptor
    assert "token" not in descriptor
    assert "materialize" not in descriptor
