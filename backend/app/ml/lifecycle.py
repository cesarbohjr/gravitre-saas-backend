"""Full-catalog lifecycle contracts, using the existing training and registry paths.

This module reports prerequisites; it does not train, toggle, promote, execute,
or introduce another intelligence engine. Unknown readiness stays unknown.
"""
from __future__ import annotations

from typing import Any

ON_DEMAND_MODELS = frozenset({"active_learning", "neuro_symbolic", "causal_impact_analyzer"})
EXTERNAL_BLOCKERS = {
    "multimodal_router": ["complete_provider_execution_and_media_validation"],
    "domain_specific_llm": ["approved_department_corpus", "held_out_domain_evaluation", "tenant_provider_training_and_routing_adapter"],
    "diffusion_model": ["configured_generation_provider", "governed_paid_generation_tool", "output_security_and_artifact_handling"],
    "federated_learning": ["explicit_cross_tenant_consent", "legal_owner_approval", "audited_secure_aggregation",
                           "validated_differential_privacy_accounting", "deployed_federated_runtime", "100_participating_tenants"],
}


def model_lifecycle_contract(name: str) -> dict[str, Any]:
    from app.ml.model_catalog import GRAVITRE_ML_CATALOG
    from app.ml.automatic_training import CONSENT_MANAGED_MODELS, AUTOMATIC_MODELS
    if name not in GRAVITRE_ML_CATALOG:
        raise ValueError("Unknown catalog model")
    if name in EXTERNAL_BLOCKERS:
        return {"mode": "specialized_infrastructure", "monitor": "technical_inventory",
                "state": "engineering_blocked", "blockers": EXTERNAL_BLOCKERS[name],
                "consent_prompt_supported": False, "automatic_training_supported": False}
    if name in ON_DEMAND_MODELS:
        return {"mode": "on_demand_advisory", "monitor": "request_data_validation",
                "state": "request_data_required", "blockers": [],
                "consent_prompt_supported": False, "automatic_training_supported": False}
    if name not in CONSENT_MANAGED_MODELS:
        # Fail visibly if a future catalog entry has not been assigned a real
        # lifecycle; never silently classify it as ready or permanently ignore it.
        return {"mode": "unassigned", "state": "engineering_blocked", "monitor": None,
                "blockers": ["lifecycle_not_assigned"], "consent_prompt_supported": False,
                "automatic_training_supported": False}
    return {"mode": "org_trained_composition" if name == "retrieval_memory_learner" else "org_trained_artifact",
            "monitor": "automatic_reconciler" if name in AUTOMATIC_MODELS else "existing_company_learning_steps",
            "state": "readiness_unverified", "blockers": [], "consent_prompt_supported": True,
            "automatic_training_supported": True,
            "prerequisite_migrations": ["20261020234133_ml_registry_model_type_compatibility"] if name == "world_model" else [],
            "migration_status": "requires_deployment_verification" if name == "world_model" else "not_applicable"}


def resolve_lifecycle(name: str, runtime: dict[str, Any], permission: dict[str, Any] | None,
                      execution: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = model_lifecycle_contract(name)
    if contract["mode"] in {"specialized_infrastructure", "on_demand_advisory", "unassigned"}:
        return contract
    result = {**contract, "artifact_loaded": runtime.get("artifact_loaded") is True,
              "inference_verified": False, "downstream_consumption": "not_verified"}
    if permission is None:
        return {**result, "state": "permission_unverified"}
    state = permission.get("consent_state")
    if state in {"paused", "revoked"}:
        return {**result, "state": "paused" if state == "paused" else "disabled"}
    if runtime.get("artifact_load_failed"):
        return {**result, "state": "failed", "failure_reason": "artifact_load_failed"}
    if permission.get("observed_count") is None:
        return {**result, "state": "data_readiness_unverified"}
    if not permission.get("candidate_data_detected") and not result["artifact_loaded"]:
        return {**result, "state": "awaiting_data"}
    if state != "approved":
        return {**result, "state": "awaiting_permission"}
    if not result["artifact_loaded"]:
        return {**result, "state": "awaiting_training_validation"}
    if (execution and execution.get("model_id") == runtime.get("deployed_model_id")
            and execution.get("version") == runtime.get("deployed_version")):
        return {**result, "state": "inference_verified", "inference_verified": True,
                "execution_evidence": execution}
    return {**result, "state": "artifact_ready_inference_unverified"}
