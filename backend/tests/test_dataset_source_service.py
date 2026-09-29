import pytest

from app.services.dataset_source_service import (
    create_dataset_source,
    validate_source_payload,
)


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self):
        self.pending = None

    def upsert(self, row, **_kwargs):
        self.pending = dict(row)
        return self

    def execute(self):
        return _Response([self.pending] if self.pending is not None else [])


class _Client:
    def __init__(self):
        self.query = _Query()

    def table(self, name):
        assert name == "training_dataset_sources"
        return self.query


def test_provider_neutral_reference_source_does_not_materialize():
    client = _Client()
    row = create_dataset_source(
        client,
        org_id="org-1",
        dataset_id="ds-1",
        provider="Example Provider",
        external_id="dataset/acme",
        access_mode="reference",
        source_uri="provider://dataset/acme",
        created_by="user-1",
    )
    assert row["provider"] == "example provider"
    assert row["external_id"] == "dataset/acme"
    assert row["access_mode"] == "reference"
    assert row["materialization_status"] == "not_requested"
    assert "token" not in row
    assert "secret" not in row


def test_sample_mode_requires_explicit_limit():
    with pytest.raises(ValueError, match="sample_limit"):
        validate_source_payload(
            provider="provider-x",
            external_id="sample",
            access_mode="sample",
        )


def test_materialized_mode_is_explicit_not_default():
    client = _Client()
    row = create_dataset_source(
        client,
        org_id="org-1",
        dataset_id="ds-1",
        provider="provider-x",
        external_id="dataset-1",
        access_mode="materialized",
    )
    assert row["materialization_status"] == "materialized"


def test_provider_name_has_no_hardcoded_vendor_semantics():
    for provider in ("huggingface", "kaggle", "internal-catalog", "partner-x"):
        payload = validate_source_payload(
            provider=provider,
            external_id="dataset-1",
            access_mode="index",
        )
        assert payload["provider"] == provider
        assert payload["access_mode"] == "index"


@pytest.mark.parametrize(
    "uri",
    (
        "https://provider.example/data?access_token=secret",
        "https://provider.example/data?api_key=secret",
        "https://provider.example/data?client_secret=secret",
    ),
)
def test_source_uri_rejects_embedded_credentials(uri):
    with pytest.raises(ValueError, match="must not contain provider credentials"):
        validate_source_payload(
            provider="provider-x",
            external_id="dataset-1",
            access_mode="reference",
            source_uri=uri,
        )
