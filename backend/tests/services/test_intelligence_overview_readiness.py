from app.services.intelligence_overview_readiness import score_readiness, _fresh


def test_connections_alone_never_certify_comprehensive_coverage():
    inputs = [
        {"vendor": "hubspot", "executable": True},
        {"vendor": "stripe", "executable": True},
        {"vendor": "zendesk", "executable": True},
    ]
    result = score_readiness(inputs)
    assert result["tier"] == "cross_system_candidate"
    assert result["connector_count"] == 3
    assert result["coverage_verified"] is False
    assert result["comprehensive"] is False
    assert "authorized_read_scope" in result["missing_evidence"]


def test_unusable_connectors_excluded_and_vendor_deduplicated():
    result = score_readiness([
        {"vendor": "hubspot", "executable": True},
        {"vendor": "hubspot", "executable": True},
        {"vendor": "stripe", "executable": False},
    ])
    assert result["connector_count"] == 1
    assert result["vendors"] == ["hubspot"]
    assert result["tier"] == "limited"


def test_missing_and_future_freshness_are_not_fresh():
    assert not _fresh(None)
    assert not _fresh("not-a-date")
    assert not _fresh("2099-01-01T00:00:00Z")
