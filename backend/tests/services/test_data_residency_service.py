"""Data residency service tests (STA-80)."""
from app.services.data_residency_service import get_org_data_region, normalize_region


def test_get_org_data_region_prefers_column():
    region = get_org_data_region({"data_region": "eu"}, data_region="us")
    assert region == "us"


def test_get_org_data_region_from_settings():
    settings = {"enterprise": {"dataResidency": {"region": "eu"}}}
    assert get_org_data_region(settings) == "eu"


def test_normalize_region_rejects_invalid():
    try:
        normalize_region("apac")
        assert False, "expected ValueError"
    except ValueError:
        pass
