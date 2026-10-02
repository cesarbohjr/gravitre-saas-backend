from copy import deepcopy
from types import SimpleNamespace

from app.marketplace.marketplace3.portfolio_readiness import _outcome_assets, portfolio_readiness_report


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
        assert row["playCount"] >= 8, slug
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


class _Table:
    def __init__(self, rows):
        self.rows = rows
    def select(self, *_):
        return self
    def in_(self, key, values):
        self.rows = [row for row in self.rows if row.get(key) in values]
        return self
    def eq(self, key, value):
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self
    def execute(self):
        return SimpleNamespace(data=deepcopy(self.rows))


class _LiveClient:
    def __init__(self):
        self.tables = {"marketplace_assets": [], "marketplace_pack_items": [],
                       "workflow_runs": [], "workflow_steps": [], "intelligence_outcome_events": []}
    def table(self, name):
        return _Table(self.tables[name])


def _deployed_pack():
    asset = _outcome_assets()[0]
    return {**vars(asset), "id": "asset-1", "org_id": None,
            "certification_level": "outcome_verified", "certification_evidence": {}}


def test_live_readiness_does_not_hide_unseeded_packs():
    report = portfolio_readiness_report(_LiveClient())
    assert report["source"] == "deployed_catalog"
    assert report["deployedPackCount"] == report["governedCount"] == 0
    assert all(row["status"] == "missing" and row["nextGate"] == "seed_catalog"
               and row["certificationLevel"] is None for row in report["packs"])


def test_live_readiness_uses_database_config_and_rejects_stale_labels():
    client = _LiveClient()
    asset = _deployed_pack()
    asset["title"] = "Tenant pilot rollout"
    client.tables["marketplace_assets"] = [asset]
    client.tables["marketplace_pack_items"] = [{"pack_asset_id": asset["id"]}]
    report = portfolio_readiness_report(client)
    row = next(row for row in report["packs"] if row["slug"] == asset["slug"])
    assert row["title"] == "Tenant pilot rollout"
    assert row["packChildCount"] == 1
    assert row["storedCertificationLevel"] == "outcome_verified"
    assert row["certificationLevel"] == "governed"
    assert row["publishReady"] is False
    assert report["deployedPackCount"] == 1
    assert asset["certification_level"] == "outcome_verified"  # read-only


def test_live_readiness_resolves_and_rechecks_recorded_runtime_proof():
    client = _LiveClient()
    asset = _deployed_pack()
    org = "00000000-0000-0000-0000-000000000001"
    run = "00000000-0000-0000-0000-000000000002"
    profiles = asset["config"]["runtime_profiles"]
    asset["certification_evidence"] = {"runtime": {
        profile["provider"]: {"orgId": org, "runIds": [run]} for profile in profiles}}
    client.tables["marketplace_assets"] = [asset]
    client.tables["workflow_runs"] = [{"id": run, "org_id": org, "status": "completed",
                                      "run_type": "execute", "environment": "production", "completed_at": "2026-10-02"}]
    client.tables["workflow_steps"] = [{"org_id": org, "run_id": run, "status": "completed",
        "output_snapshot": {"success": True, "invoke_action": action,
                            "verification": {"verified": True, "status": "verified"}}}
        for profile in profiles for action in profile["actions"]]
    def current():
        return next(row for row in portfolio_readiness_report(client)["packs"] if row["slug"] == asset["slug"])
    assert current()["certificationLevel"] == "production_verified"
    client.tables["workflow_runs"][0]["run_type"] = "dry_run"
    assert current()["certificationLevel"] == "governed"


def test_malformed_deployed_pack_does_not_hide_other_packs():
    client = _LiveClient()
    asset = _deployed_pack()
    asset["config"] = {}
    client.tables["marketplace_assets"] = [asset]
    report = portfolio_readiness_report(client)
    assert report["packCount"] == 8
    row = next(row for row in report["packs"] if row["slug"] == asset["slug"])
    assert row["blockingFindingCodes"] == ["INVALID_CONFIG"]
    assert row["publishReady"] is False
