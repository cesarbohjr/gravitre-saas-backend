from datetime import datetime, timezone
from unittest.mock import MagicMock
from app.marketplace.marketplace3.production_evidence import collect_production_evidence


def _collect(rows):
    client = MagicMock()
    query = client.table.return_value
    query.select.return_value = query
    query.eq.return_value = query
    query.gte.return_value = query
    query.limit.return_value = query
    query.execute.return_value.data = rows
    check_query = MagicMock()
    for method in ("select", "eq", "gte", "order", "limit"):
        getattr(check_query, method).return_value = check_query
    check_query.execute.return_value.data = []
    client.table.side_effect = lambda name: query if name == "workflow_runs" else check_query
    result = collect_production_evidence(client, org_id="org", asset_id="pack", config_digest="digest")
    assert query.eq.call_args_list[0].args == ("org_id", "org")
    return result


def _row(**updates):
    row = {"id": "run", "org_id": "org", "status": "completed", "environment": "production",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {"invoke_action": "hubspot.contacts.update",
            "marketplace_certification": {"asset_id": "pack", "config_digest": "digest", "fixture": False},
            "verification": {"verified": True, "method": "entity_get", "resource_id": "contact-1", "action": "hubspot.contacts.update"}}}
    row.update(updates)
    return row


def test_action_proof_does_not_invent_install_or_permissions_or_kpi_evidence():
    proof = _collect([_row()])
    assert proof.actions == {"hubspot.contacts.update"}
    assert not proof.covers({"hubspot.contacts.update"})


def test_wrong_org_environment_and_fixture_never_become_action_evidence():
    fixture = _row()
    fixture["parameters"]["marketplace_certification"]["fixture"] = True
    assert not _collect([fixture, _row(org_id="foreign"), _row(environment="sandbox")]).actions


def test_unattributed_verified_boolean_does_not_count():
    row = _row()
    row["parameters"]["verification"] = {"verified": True}
    assert not _collect([row]).actions


def test_old_digest_and_accepted_response_do_not_count():
    row = _row()
    row["parameters"]["marketplace_certification"]["config_digest"] = "old"
    assert not _collect([row, _row(status="verifying")]).actions


def test_independent_checks_and_measured_kpi_are_required_and_bound():
    from types import SimpleNamespace
    from app.marketplace.marketplace3.production_evidence import REQUIRED_CHECKS
    stamp = datetime.now(timezone.utc).isoformat()
    check_rows = [{"org_id": "org", "asset_id": "pack", "config_digest": "digest", "check_kind": kind,
                   "environment": "production", "passed": True, "evidence_ref": "artifact-"+kind, "checked_at": stamp}
                  for kind in REQUIRED_CHECKS]
    measured = {"org_id": "org", "workflow_run_id": "run", "measurement_status": "recorded", "before_value": 1,
        "after_value": 2, "measured_at": stamp, "metadata": {"contract": "play_business_result/v1", "verified": True,
        "verification_state": "VERIFIED SUCCESS", "verification_method": "entity_get", "source_records": [{"id": "record"}],
        "evidence_ids": ["receipt"], "metric_key": "recovered", "play_key": "recover"}}
    datasets = {"workflow_runs": [_row()], "marketplace_outcome_pack_checks": check_rows, "intelligence_outcome_events": [measured]}
    client = MagicMock()
    def table(name):
        query = MagicMock()
        for method in ("select", "eq", "gte", "order", "limit", "in_"):
            getattr(query, method).return_value = query
        query.execute.return_value.data = datasets[name]
        return query
    client.table.side_effect = table
    config = SimpleNamespace(plays=[SimpleNamespace(key="recover", kpi_keys=["recovered"], outcome_events=["recovery_confirmed"])])
    proof = collect_production_evidence(client, org_id="org", asset_id="pack", config_digest="digest", config=config)
    assert proof.covers({"hubspot.contacts.update"})
    assert proof.measured_outcome_events == {"recovery_confirmed"}
    measured["workflow_run_id"] = "unrelated"
    check_rows.insert(0, {**check_rows[0], "passed": False})
    proof = collect_production_evidence(client, org_id="org", asset_id="pack", config_digest="digest", config=config)
    assert not proof.covers({"hubspot.contacts.update"})
    assert not proof.measured_outcome_events
