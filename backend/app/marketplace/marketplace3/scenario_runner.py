"""Record scenario checks from canonical installations, executions and readbacks.

This runner never grants execution authority or accepts caller proof. It inspects
normal governed runs; pending approvals must be resolved in their existing UI.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import json

from app.core.safe_dict import safe_normalize_stored_dict as as_dict
from app.core.io_pool import run_io
from app.marketplace.marketplace3.certification_store import outcome_pack_config_digest
from app.marketplace.marketplace3.permissions_probe import probe_outcome_pack_permissions
from app.marketplace.marketplace3.production_evidence import collect_production_evidence, current_pack_workflows



def _collect_scenario_facts(client, *, org_id, asset, config):
    asset_id = str(asset["id"])
    digest = outcome_pack_config_digest(config)
    workflows = current_pack_workflows(client, org_id=org_id, asset_id=asset_id, digest=digest, config=config)
    expected = {play.key for play in config.plays}
    installations = (client.table("play_installations").select("id,org_id,play_key,environment_name,configuration,status")
        .eq("org_id", org_id).eq("environment_name", "production").limit(1000).execute().data or [])
    installed = {row.get("play_key") for row in installations if row.get("org_id") == org_id
        and row.get("environment_name") == "production" and row.get("status") == "ready"
        and as_dict(row.get("configuration")).get("marketplaceAssetId") == asset_id
        and as_dict(row.get("configuration")).get("marketplaceConfigDigest") == digest}
    bound = {as_dict(row.get("config")).get("marketplacePlayKey") for row in workflows}
    proof = collect_production_evidence(client, org_id=org_id, asset_id=asset_id, config_digest=digest, config=config)
    # Only canonical terminal gate failures with no completed consequential steps
    # demonstrate the negative path. A provider failure after a write is not safe.
    failure_refs = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    if workflows:
        runs = (client.table("workflow_runs").select("id,org_id,workflow_id,status,environment,run_type,definition_snapshot")
            .eq("org_id", org_id).eq("environment", "production").eq("run_type", "execute")
            .in_("workflow_id", [w["id"] for w in workflows]).gte("created_at", cutoff).limit(1000).execute().data or [])
        definitions = {w["id"]: w["definition"] for w in workflows}
        for run in runs:
            if (run.get("org_id") != org_id or run.get("environment") != "production" or run.get("run_type") != "execute"
                    or run.get("status") not in {"failed", "cancelled"}
                    or run.get("definition_snapshot") != definitions.get(run.get("workflow_id"))):
                continue
            steps = (client.table("workflow_steps").select("org_id,status,step_type,error_code,output_snapshot")
                     .eq("org_id", org_id).eq("run_id", run["id"]).execute().data or [])
            from app.services.outcome_verification import is_write_action
            from app.connectors.action_catalog.registry import get_action_spec
            def safe_step(step):
                output = as_dict(step.get("output_snapshot"))
                action = str(output.get("invoke_action") or "")
                spec = get_action_spec(action) if action else None
                return (step.get("org_id") == org_id and (step.get("status") not in {"completed", "running"}
                    or (step.get("step_type") == "invoke_tool" and spec is not None and not is_write_action(action))))
            if (steps and all(safe_step(step) for step in steps)
                    and any(step.get("error_code") in {"APPROVAL_REQUIRED", "APPROVAL_DENIED", "POLICY_DENIED", "TOOL_NOT_ALLOWED", "CANCELLED_BEFORE_INVOKE"} for step in steps)):
                failure_refs.append(str(run["id"]))
    checks = {
        "fresh_install_passed": bool(expected) and expected <= installed and expected <= bound,
        "golden_path_passed": bool(expected) and expected <= proof.play_keys,
        "failure_path_passed": bool(failure_refs),
        "permissions_passed": False,
        "kpi_reconciliation_passed": bool(config.outcome_contract.kpis) and {k.key for k in config.outcome_contract.kpis if k.kind in {"business", "funnel"}} <= proof.measured_metric_keys,
        "source_of_record_verification_passed": bool(proof.actions) and {a for p in config.runtime_profiles for a in p.actions} <= proof.actions,
    }
    return checks, proof, workflows, failure_refs


async def record_executed_scenarios(client, settings, *, org_id, asset, config, access_token):
    checks, proof, workflows, failure_refs = await run_io(_collect_scenario_facts, client,
        org_id=org_id, asset=asset, config=config)
    asset_id = str(asset["id"])
    digest = outcome_pack_config_digest(config)
    try:
        permission = await probe_outcome_pack_permissions(client, settings, org_id=org_id, asset_id=asset_id, access_token=access_token)
    except Exception:
        permission = {"passed": False, "reason": "permission_probe_unavailable"}
    checks["permissions_passed"] = permission.get("passed") is True
    batch = str(uuid4())
    receipts = [{"org_id": org_id, "asset_id": asset_id, "config_digest": digest, "check_kind": kind,
        "environment": "production", "passed": passed,
        "evidence_ref": json.dumps({"scenario_id": batch, "check": kind,
            "run_ids": sorted(set(proof.run_ids) | set(failure_refs)),
            "workflow_ids": sorted(str(row["id"]) for row in workflows),
            "verified_play_keys": sorted(proof.play_keys), "measured_metric_keys": sorted(proof.measured_metric_keys),
            "permission_controls": {key: permission.get(key) for key in ("ownRowId", "foreignControlRowId", "ownVisible", "foreignHidden", "reason")}}, sort_keys=True),
        "checked_at": datetime.now(timezone.utc).isoformat()} for kind, passed in checks.items()]
    result = await run_io(lambda: client.table("marketplace_outcome_pack_checks").insert(receipts).execute())
    if len(result.data or []) != len(receipts):
        raise RuntimeError("Scenario receipts were not durably recorded")
    return {"scenarioId": batch, "checks": checks, "runIds": list(proof.run_ids),
            "missingPlays": sorted({play.key for play in config.plays} - proof.play_keys), "permissionReason": permission.get("reason")}
