from app.marketplace.marketplace3.portfolio_readiness import portfolio_readiness_report


def test_marketplace3_portfolio_readiness_quantifies_all_first_party_packs() -> None:
    report = portfolio_readiness_report()
    assert report["packCount"] == 8
    assert report["fixtureReadyCount"] == 8
    assert report["governedCount"] == 8
    assert report["productionVerifiedCount"] == 0
    assert report["outcomeVerifiedCount"] == 0
    assert report["publishReadyCount"] == 0
    assert report["draftInternalCount"] == 8

    by_slug = {row["slug"]: row for row in report["packs"]}
    assert {
        "msp-service-desk-3",
        "security-operations-3",
        "revenue-operations-3",
        "customer-success-support-3",
        "finance-operations-3",
        "marketing-operations-3",
        "people-it-operations-3",
        "executive-command-center-3",
    } == set(by_slug)

    msp = by_slug["msp-service-desk-3"]
    assert msp["playCount"] == 8
    assert msp["agentCount"] == 7
    assert msp["kpiCount"] >= 16
    assert msp["fixturePassed"] is True
    assert msp["certificationLevel"] == "governed"
    assert msp["nextGate"] == "live_production_runtime_evidence"

    for slug, row in by_slug.items():
        assert row["fixturePassed"] is True, slug
        assert row["failedFixtureChecks"] == [], slug
        assert row["certificationLevel"] == "governed", slug
        assert row["publishReady"] is False, slug
        assert row["status"] == "draft", slug
        assert row["visibility"] == "internal", slug
        assert row["playCount"] >= 7, slug
        assert row["agentCount"] >= 2, slug
        assert row["kpiCount"] >= 7, slug
        assert row["knowledgeCount"] >= 1, slug
        assert row["runtimeProfileCount"] >= 1, slug
        assert row["nextGate"] == "live_production_runtime_evidence", slug


def test_marketplace3_portfolio_has_no_static_certification_failures() -> None:
    report = portfolio_readiness_report()
    for row in report["packs"]:
        # A governed pack may still be blocked from publication solely because
        # live production evidence is intentionally absent. Static fixture and
        # contract failures must already be zero.
        assert row["failedFixtureChecks"] == [], row["slug"]
        assert row["blockingFindingCodes"] == [], row["slug"]
