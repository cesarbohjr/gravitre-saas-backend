from pathlib import Path

import pytest

from app.training.dataset_sources import (
    DatasetSourceAccessMode,
    DatasetSourceRef,
    list_dataset_sources,
    register_dataset_source,
)

ROOT = Path(__file__).resolve().parents[1]


def test_source_contract_defaults_to_reference_metadata_not_fetch():
    source = DatasetSourceRef(
        provider="external-catalog",
        locator="namespace/resource",
        access_mode=DatasetSourceAccessMode.REFERENCE,
        revision="v1",
        license_name="example-license",
        provenance={"publisher": "example"},
    )
    payload = source.storage_payload(
        org_id="org-1",
        dataset_id="dataset-1",
        created_by="user-1",
    )
    assert payload["provider"] == "external-catalog"
    assert payload["access_mode"] == "reference"
    assert payload["status"] == "configured"
    assert "token" not in str(payload).lower()
    assert "password" not in str(payload).lower()


@pytest.mark.parametrize(
    "metadata",
    [
        {"access_token": "secret"},
        {"refresh_token": "secret"},
        {"api_key": "secret"},
        {"client_secret": "secret"},
        {"password": "secret"},
    ],
)
def test_source_contract_rejects_credentials_in_metadata(metadata):
    source = DatasetSourceRef(
        provider="provider",
        locator="dataset",
        access_mode=DatasetSourceAccessMode.REFERENCE,
        source_metadata=metadata,
    )
    with pytest.raises(ValueError, match="must not contain credentials"):
        source.validate()


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = list(rows)
        self.pending = None

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if str(row.get(key)) == str(value)]
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def upsert(self, payload, **_kwargs):
        self.pending = dict(payload)
        return self

    def execute(self):
        if self.pending is not None:
            return _Response([self.pending])
        return _Response(self.rows)


class _Client:
    def __init__(self):
        self.datasets = [{"id": "dataset-1", "org_id": "org-1"}]
        self.sources = []

    def table(self, name):
        if name == "training_datasets":
            return _Query(self.datasets)
        if name == "training_dataset_sources":
            return _Query(self.sources)
        raise AssertionError(name)


def test_registration_reuses_existing_training_dataset():
    client = _Client()
    row = register_dataset_source(
        client,
        org_id="org-1",
        dataset_id="dataset-1",
        created_by="user-1",
        source=DatasetSourceRef(
            provider="external-catalog",
            locator="namespace/resource",
            access_mode=DatasetSourceAccessMode.INDEX,
        ),
    )
    assert row["dataset_id"] == "dataset-1"
    assert row["access_mode"] == "index"


def test_migration_is_provider_neutral_and_rls_scoped():
    sql = (
        ROOT.parent
        / "supabase"
        / "migrations"
        / "20260929150000_training_dataset_sources.sql"
    ).read_text().lower()
    assert "training_dataset_sources" in sql
    assert "enable row level security" in sql
    assert "organization_members" in sql
    assert "access_token" not in sql
    assert "refresh_token" not in sql
    assert "api_key" not in sql
    assert "huggingface" not in sql


def test_training_router_registers_source_without_starting_fetch():
    source = (ROOT / "app" / "routers" / "training.py").read_text()
    assert '/datasets/{dataset_id}/sources' in source
    assert '"fetchStarted": False' in source
    assert '"credentialsStored": False' in source


@pytest.mark.parametrize(
    "metadata",
    [
        {"token": "secret"},
        {"authorization": "Bearer secret"},
        {"nested": {"secret": "value"}},
        {"nested": [{"password": "value"}]},
    ],
)
def test_source_contract_rejects_generic_or_nested_secret_keys(metadata):
    source = DatasetSourceRef(
        provider="provider",
        locator="dataset",
        access_mode=DatasetSourceAccessMode.REFERENCE,
        source_metadata=metadata,
    )
    with pytest.raises(ValueError, match="must not contain credentials"):
        source.validate()
