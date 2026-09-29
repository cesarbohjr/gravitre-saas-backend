import pytest

from app.training.dataset_sources import DatasetSourceAccessMode, DatasetSourceRef
from app.training.providers.huggingface import HuggingFaceDatasetAdapter


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_huggingface_sample_is_bounded_and_uses_dataset_viewer_rows():
    calls = []

    def fake_get(url, *, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        if url.endswith("/splits"):
            return _Response({"splits": [{"config": "default", "split": "train"}]})
        assert url.endswith("/rows")
        assert params["length"] == 100
        return _Response(
            {"rows": [{"row": {"id": i}} for i in range(100)]}
        )

    adapter = HuggingFaceDatasetAdapter(request_get=fake_get)
    source = DatasetSourceRef(
        provider="huggingface",
        locator="namespace/dataset",
        access_mode=DatasetSourceAccessMode.SAMPLE,
    )
    sample = adapter.sample(source, limit=500)

    assert len(sample.rows) == 100
    assert sample.truncated is True
    assert sample.provenance["materialized"] is False
    assert sample.provenance["access"] == "dataset_viewer_rows"
    assert [call[0].rsplit("/", 1)[-1] for call in calls] == ["splits", "rows"]


def test_huggingface_adapter_uses_supplied_config_split_without_discovery():
    calls = []

    def fake_get(url, *, params, headers, timeout):
        calls.append((url, params))
        return _Response({"rows": [{"row": {"text": "a"}}]})

    adapter = HuggingFaceDatasetAdapter(request_get=fake_get)
    source = DatasetSourceRef(
        provider="huggingface",
        locator="namespace/dataset",
        access_mode=DatasetSourceAccessMode.SAMPLE,
        source_metadata={"config": "subset", "split": "validation"},
    )
    sample = adapter.sample(source, limit=1)

    assert sample.rows == ({"text": "a"},)
    assert len(calls) == 1
    assert calls[0][0].endswith("/rows")
    assert calls[0][1]["config"] == "subset"
    assert calls[0][1]["split"] == "validation"


@pytest.mark.parametrize("status_code", [401, 403])
def test_huggingface_gated_or_private_access_fails_closed(status_code):
    def fake_get(*_args, **_kwargs):
        return _Response({"error": "not accessible"}, status_code=status_code)

    adapter = HuggingFaceDatasetAdapter(request_get=fake_get)
    source = DatasetSourceRef(
        provider="huggingface",
        locator="owner/gated",
        access_mode=DatasetSourceAccessMode.SAMPLE,
        source_metadata={"config": "default", "split": "train"},
    )

    with pytest.raises(PermissionError, match="will not request or bypass gated access"):
        adapter.sample(source, limit=5)


def test_huggingface_token_is_runtime_only_and_not_source_metadata():
    seen = {}

    def fake_get(url, *, params, headers, timeout):
        seen["headers"] = headers
        return _Response({"rows": []})

    adapter = HuggingFaceDatasetAdapter(token="runtime-secret", request_get=fake_get)
    source = DatasetSourceRef(
        provider="huggingface",
        locator="namespace/dataset",
        access_mode=DatasetSourceAccessMode.SAMPLE,
        source_metadata={"config": "default", "split": "train"},
    )
    payload = source.storage_payload(
        org_id="org-1",
        dataset_id="dataset-1",
        created_by="user-1",
    )
    adapter.sample(source, limit=1)

    assert seen["headers"]["Authorization"] == "Bearer runtime-secret"
    assert "runtime-secret" not in str(payload)


def test_huggingface_materialization_is_explicitly_disabled():
    adapter = HuggingFaceDatasetAdapter(request_get=lambda *_a, **_k: None)
    source = DatasetSourceRef(
        provider="huggingface",
        locator="namespace/dataset",
        access_mode=DatasetSourceAccessMode.MATERIALIZE,
    )
    with pytest.raises(ValueError, match="materialization is not enabled"):
        adapter.validate_source(source)
