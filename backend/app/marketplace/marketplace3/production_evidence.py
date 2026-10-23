"""Read-only, configuration-bound certification proof from canonical run ledgers.

Caller-provided booleans, runtime profile labels and fixture runs are never proof.
Missing ledger dimensions deliberately prevent production certification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from math import isfinite
from copy import deepcopy

from app.core.safe_dict import safe_normalize_stored_dict
from app.services.outcome_verification import evidence_is_verified

REQUIRED_CHECKS = (
    "fresh_install_passed", "golden_path_passed", "failure_path_passed",
    "permissions_passed", "kpi_reconciliation_passed", "source_of_record_verification_passed",
)


@dataclass(frozen=True)
class ProductionEvidence:
    """Server-collected evidence, never deserialized from an API request."""
    org_id: str
    asset_id: str
    config_digest: str
    actions: frozenset[str] = frozenset()
    checks: dict[str, bool] = field(default_factory=dict)
    run_ids: tuple[str, ...] = ()
    measured_outcome_events: frozenset[str] = frozenset()

    play_keys: frozenset[str] = frozenset()
    measured_metric_keys: frozenset[str] = frozenset()

    def covers(self, actions: set[str]) -> bool:
        return bool(actions) and actions <= self.actions and all(self.checks.get(k) is True for k in REQUIRED_CHECKS)

    def as_dict(self) -> dict[str, Any]:
        return {"source": "canonical_production_ledgers", "org_id": self.org_id,
                "asset_id": self.asset_id, "config_digest": self.config_digest,
                "verified_actions": sorted(self.actions), "verified_play_keys": sorted(self.play_keys),
                "measured_metric_keys": sorted(self.measured_metric_keys), "checks": self.checks,
                "run_ids": list(self.run_ids), "verified_outcome_events": sorted(self.measured_outcome_events)}


def _matches_current_play(row, *, config, org_id, asset_id):
    from app.marketplace.service import _resolve_workflow_steps, marketplace_entity_id
    key = safe_normalize_stored_dict(row.get("config")).get("marketplacePlayKey")
    play = next((p for p in config.plays if p.key == key), None)
    if play is None:
        return False
    agents = {a.seed_label: marketplace_entity_id(org_id, asset_id, a.seed_label or "agent") for a in getattr(config, "agents", [])}
    providers = {str(step.get("requires_connector")): "bound" for step in play.workflow_steps if step.get("requires_connector")}
    expected = _resolve_workflow_steps(deepcopy(play.workflow_steps), agent_ids=agents, connector_ids=providers)
    actual = deepcopy(safe_normalize_stored_dict(row.get("definition")).get("steps", []))
    for steps in (expected, actual):
        for step in steps:
            if isinstance(step.get("config"), dict):
                step["config"].pop("connector_id", None)
    for step in expected:
        if step.get("type") == "agent":
            step.setdefault("metadata", {}).setdefault("briefing_from_steps", True)
    if actual != expected:
        return False
    from app.marketplace.pack_prewiring import definition_with_sequential_graph
    expected_definition = definition_with_sequential_graph(expected)
    actual_definition = deepcopy(safe_normalize_stored_dict(row.get("definition")))
    def without_connection_ids(value):
        if isinstance(value, dict):
            return {key: without_connection_ids(item) for key, item in value.items() if key != "connector_id"}
        if isinstance(value, list):
            return [without_connection_ids(item) for item in value]
        return value
    return without_connection_ids(actual_definition) == without_connection_ids(expected_definition)


def current_pack_workflows(client, *, org_id, asset_id, digest, config=None):
    rows = (client.table("workflow_defs").select("id,org_id,config,definition")
            .eq("org_id", org_id).contains("config", {"marketplaceAssetId": asset_id}).limit(1000).execute().data or [])
    return [row for row in rows if row.get("org_id") == org_id
            and safe_normalize_stored_dict(row.get("config")).get("marketplaceAssetId") == asset_id
            and safe_normalize_stored_dict(row.get("config")).get("marketplaceConfigDigest") == digest
            and (config is None or _matches_current_play(row, config=config, org_id=org_id, asset_id=asset_id))]


def _scenario_checks(client, *, org_id, asset_id, config_digest, cutoff):
    check_rows = (client.table("marketplace_outcome_pack_checks")
        .select("org_id,asset_id,config_digest,check_kind,environment,passed,evidence_ref,checked_at")
        .eq("org_id", org_id).eq("asset_id", asset_id).eq("config_digest", config_digest)
        .eq("environment", "production").gte("checked_at", cutoff.isoformat())
        .order("checked_at", desc=True).limit(1000).execute().data or [])
    checks: dict[str, bool] = {}
    for row in check_rows:
        kind = row.get("check_kind")
        if kind not in REQUIRED_CHECKS or kind in checks:
            continue
        if (row.get("org_id") != org_id or row.get("asset_id") != asset_id
                or row.get("config_digest") != config_digest or row.get("environment") != "production"):
            continue
        try:
            stamp = datetime.fromisoformat(str(row.get("checked_at")).replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp < cutoff or stamp > datetime.now(timezone.utc):
                continue
        except (TypeError, ValueError):
            continue
        checks[kind] = row.get("passed") is True and bool(str(row.get("evidence_ref") or "").strip())
    return checks


def collect_production_evidence(client, *, org_id, asset_id, config_digest, config=None):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    checks = _scenario_checks(client, org_id=org_id, asset_id=asset_id, config_digest=config_digest, cutoff=cutoff)
    if config is None:
        return ProductionEvidence(org_id, asset_id, config_digest, checks=checks)
    from app.services.outcome_verification import is_write_action
    from app.connectors.action_catalog.registry import get_action_spec
    workflows = current_pack_workflows(client, org_id=org_id, asset_id=asset_id, digest=config_digest, config=config)
    expected = {play.key: play for play in config.plays}
    actions, play_keys, run_ids = set(), set(), []
    if workflows:
        runs = (client.table("workflow_runs").select("id,org_id,workflow_id,status,environment,run_type,definition_snapshot,created_at")
            .eq("org_id", org_id).eq("environment", "production").eq("run_type", "execute")
            .in_("workflow_id", [w["id"] for w in workflows]).gte("created_at", cutoff.isoformat()).limit(1000).execute().data or [])
        bindings = {w["id"]: w for w in workflows}
        for run in runs:
            binding = bindings.get(run.get("workflow_id"), {})
            key = safe_normalize_stored_dict(binding.get("config")).get("marketplacePlayKey")
            if (run.get("org_id") != org_id or run.get("environment") != "production" or run.get("run_type") != "execute"
                    or run.get("status") != "completed" or key not in expected
                    or run.get("definition_snapshot") != binding.get("definition")):
                continue
            try:
                stamp = datetime.fromisoformat(str(run.get("created_at")).replace("Z", "+00:00"))
                if stamp.tzinfo is None or not cutoff <= stamp <= datetime.now(timezone.utc):
                    continue
            except (TypeError, ValueError):
                continue
            steps = (client.table("workflow_steps").select("id,org_id,step_id,status,output_snapshot")
                .eq("org_id", org_id).eq("run_id", run["id"]).execute().data or [])
            definitions = {step["id"]: step for step in (binding.get("definition") or {}).get("steps", [])}
            proven = set()
            for step in steps:
                definition = definitions.get(step.get("step_id"), {})
                declared = safe_normalize_stored_dict(definition.get("config"))
                action = str(declared.get("action") or declared.get("tool_action") or "")
                output = safe_normalize_stored_dict(step.get("output_snapshot"))
                if (step.get("org_id") != org_id or step.get("status") != "completed"
                        or definition.get("type") != "invoke_tool" or output.get("invoke_action") != action
                        or output.get("success") is False or get_action_spec(action) is None):
                    continue
                verification = safe_normalize_stored_dict(output.get("verification"))
                if is_write_action(action) and (not evidence_is_verified(verification)
                        or verification.get("action") not in (None, action)
                        or not (verification.get("resource_id") or verification.get("entity_id"))):
                    continue
                proven.add(action)
            required = {str(s.get("config", {}).get("action") or s.get("config", {}).get("tool_action") or "")
                        for s in expected[key].workflow_steps if s.get("type") == "invoke_tool"}
            actions.update(proven)
            if required and required <= proven:
                play_keys.add(key)
            if proven:
                run_ids.append(str(run["id"]))
    # Independent scenario receipts retain the same ownership/freshness rules.
    measured_events, metrics = set(), set()
    if run_ids:
        rows = (client.table("intelligence_outcome_events").select("org_id,workflow_run_id,measurement_status,before_value,after_value,metadata,measured_at")
                .eq("org_id", org_id).eq("outcome_event", "play_business_result").eq("measurement_status", "recorded")
                .in_("workflow_run_id", run_ids).gte("measured_at", cutoff.isoformat()).limit(1000).execute().data or [])
        for row in rows:
            meta = safe_normalize_stored_dict(row.get("metadata"))
            play = expected.get(meta.get("play_key"))
            allowed_metrics = set(play.kpi_keys) if play else set()
            play_actions = {s.get("config", {}).get("action") for s in play.workflow_steps if s.get("type") == "invoke_tool"} if play else set()
            for recipe in getattr(config, "verification_recipes", []):
                if recipe.key == meta.get("recipe_key") and play_actions.intersection(recipe.match_actions):
                    allowed_metrics.update(c.metric_key for c in recipe.contributions)
            if (row.get("org_id") != org_id or str(row.get("workflow_run_id")) not in run_ids or row.get("measurement_status") != "recorded"
                    or play is None or meta.get("contract") != "play_business_result/v1" or meta.get("verified") is not True
                    or meta.get("verification_state") != "VERIFIED SUCCESS" or not meta.get("verification_method")
                    or not meta.get("source_records") or not meta.get("evidence_ids") or meta.get("metric_key") not in allowed_metrics):
                continue
            try:
                stamp = datetime.fromisoformat(str(row.get("measured_at")).replace("Z", "+00:00"))
                if stamp.tzinfo is None or not cutoff <= stamp <= datetime.now(timezone.utc) or not all(isfinite(float(row[k])) for k in ("before_value", "after_value")):
                    continue
            except (TypeError, ValueError, KeyError):
                continue
            metrics.add(meta["metric_key"])
            measured_events.update(play.outcome_events)
    for metric in getattr(getattr(config, "outcome_contract", None), "kpis", []):
        if metric.aggregation == "ratio" and metric.numerator in metrics and metric.denominator in metrics:
            metrics.add(metric.key)
    return ProductionEvidence(org_id, asset_id, config_digest, frozenset(actions), checks,
        tuple(run_ids), frozenset(measured_events), frozenset(play_keys), frozenset(metrics))
