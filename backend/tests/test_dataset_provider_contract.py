import pytest

from app.training.dataset_provider import (
    DatasetSourceCapabilities,
    assert_source_mode_supported,
    bounded_sample_limit,
)
from app.training.dataset_sources import DatasetSourceAccessMode, DatasetSourceRef


def test_sampling_is_bounded_before_provider_call():
    caps = DatasetSourceCapabilities(sample=True, max_sample_records=100)
    assert bounded_sample_limit(10, caps) == 10
    assert bounded_sample_limit(250, caps) == 100
    assert bounded_sample_limit(1000, DatasetSourceCapabilities(sample=True)) == 500


def test_materialization_is_not_supported_by_default():
    source = DatasetSourceRef(
        provider="external",
        locator="resource",
        access_mode=DatasetSourceAccessMode.MATERIALIZE,
    )
    with pytest.raises(ValueError, match="does not support"):
        assert_source_mode_supported(source, DatasetSourceCapabilities())


def test_reference_is_safe_default_capability():
    source = DatasetSourceRef(
        provider="external",
        locator="resource",
        access_mode=DatasetSourceAccessMode.REFERENCE,
    )
    assert_source_mode_supported(source, DatasetSourceCapabilities())


def test_zero_or_negative_sample_limits_are_rejected():
    with pytest.raises(ValueError, match="at least 1"):
        bounded_sample_limit(0, DatasetSourceCapabilities(sample=True))
