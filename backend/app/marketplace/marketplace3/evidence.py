"""Marketplace 3.0 certification evidence.

Schema validity, runtime certification, and measured business outcomes are separate
truths. This module turns immutable evidence references into certification inputs
without trusting tags or self-declared status.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.marketplace.marketplace3.certification import (
    OutcomePackCertification,
    certify_outcome_pack,
)
from app.marketplace.schemas import OutcomePackAssetConfig
from app.plays.outcomes import PLAY_BUSINESS_RESULT_EVENT, BusinessResultStatus


class MarketplaceCertificationEvidenceError(Exception):
    code = "MARKETPLACE_CERTIFICATION_EVIDENCE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _outcome_config(asset: dict[str, Any]) -> OutcomePackAssetConfig:
    if str(asset.get("asset_type") or "") != "outcome_pack":
        raise MarketplaceCertificationEvidenceError(
            "Certification evidence is only valid for Outcome Packs",
            code="INVALID_ASSET_TYPE",
        )
    raw = asset.get("config")
    if not isinstance(raw, dict):
        raise MarketplaceCertificationEvidenceError(
            "Outcome Pack config is missing",
            code="INVALID_CONFIG",
        )
    try:
        return OutcomePackAssetConfig.model_validate(raw)
    except Exception as exc:
        raise MarketplaceCertificationEvidenceError(
            "Outcome Pack config is invalid",
            code="INVALID_CONFIG",
        ) from exc


def _asset_version(asset: dict[str, Any]) -> int:
    return max(1, int(asset.get("current_version") or 1))


def list_runtime_evidence(
    client: Any,
    asset_id: str,
    *,
    asset_version: int,
) -> dict[str, dict[str, Any]]:
    rows = (
        client.table("marketplace_certification_evidence")
        .select("id, provider, environment, evidence_ref, verified_actions, metadata, created_at")
        .eq("asset_id", asset_id)
        .eq("asset_version", int(asset_version))
        .eq("evidence_kind", "runtime")
        .order("created_at", desc=False)
        .execute()
        .data
        or []
    )
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        provider = str(row.get("provider") or "").strip()
        if not provider:
            continue
        target = grouped.setdefault(
            provider,
            {
                "environment": "production",
                "evidence_ref": "",
                "evidence_refs": [],
                "verified_actions": [],
            },
        )
        ref = str(row.get("evidence_ref") or "").strip()
        if ref and ref not in target["evidence_refs"]:
            target["evidence_refs"].append(ref)
        for action in row.get("verified_actions") or []:
            value = str(action or "").strip()
            if value and value not in target["verified_actions"]:
                target["verified_actions"].append(value)
        if str(row.get("environment") or "").strip().lower() != "production":
            target["environment"] = str(row.get("environment") or "").strip().lower()
    for target in grouped.values():
        target["evidence_ref"] = " | ".join(target.pop("evidence_refs", []))
    return grouped


def verified_outcome_evidence(
    client: Any,
    asset: dict[str, Any],
) -> dict[str, Any]:
    config = _outcome_config(asset)
    play_keys = {play.key for play in config.plays}
    rows = (
        client.table("intelligence_outcome_events")
        .select("id, outcome_event, entity_id, metadata, measured_at, measurement_status")
        .eq("org_id", str(asset.get("org_id") or ""))
        .eq("outcome_event", PLAY_BUSINESS_RESULT_EVENT)
        .execute()
        .data
        or []
    )
    events: set[str] = set()
    evidence_ids: list[str] = []
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        play_key = str(metadata.get("play_key") or "").strip()
        if play_key not in play_keys:
            continue
        state = str(metadata.get("verification_state") or "").strip().upper()
        if state != BusinessResultStatus.VERIFIED_SUCCESS.value:
            continue
        source_records = metadata.get("source_records") or []
        metric_key = str(metadata.get("metric_key") or "").strip()
        outcome_type = str(metadata.get("outcome_type") or "").strip()
        if not source_records or not metric_key or not outcome_type:
            continue
        events.add(outcome_type)
        row_id = str(row.get("id") or "").strip()
        if row_id:
            evidence_ids.append(row_id)
    return {
        "verified_outcome_events": sorted(events),
        "evidence_ids": evidence_ids,
    }


def _config_with_evidence_status(
    config: OutcomePackAssetConfig,
    runtime_evidence: dict[str, dict[str, Any]],
) -> OutcomePackAssetConfig:
    payload = deepcopy(config.model_dump(mode="json"))
    for profile in payload.get("runtime_profiles") or []:
        provider = str(profile.get("provider") or "").strip()
        evidence = runtime_evidence.get(provider)
        if not evidence:
            continue
        verified = {
            str(value).strip()
            for value in (evidence.get("verified_actions") or [])
            if str(value).strip()
        }
        required = {
            str(value).strip()
            for value in (profile.get("actions") or [])
            if str(value).strip()
        }
        if (
            str(evidence.get("environment") or "").strip().lower() == "production"
            and str(evidence.get("evidence_ref") or "").strip()
            and required.issubset(verified)
        ):
            profile["status"] = "production_verified"
    return OutcomePackAssetConfig.model_validate(payload)


def certification_report_for_asset(
    client: Any,
    asset: dict[str, Any],
) -> OutcomePackCertification:
    config = _outcome_config(asset)
    runtime_evidence = list_runtime_evidence(
        client,
        str(asset["id"]),
        asset_version=_asset_version(asset),
    )
    evidenced_config = _config_with_evidence_status(config, runtime_evidence)
    outcomes = verified_outcome_evidence(client, asset)
    return certify_outcome_pack(
        evidenced_config,
        runtime_evidence=runtime_evidence,
        outcome_evidence=outcomes,
    )


def record_runtime_evidence(
    client: Any,
    *,
    asset: dict[str, Any],
    provider: str,
    environment: str,
    evidence_ref: str,
    verified_actions: list[str],
    actor_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = _outcome_config(asset)
    provider_name = provider.strip()
    env = environment.strip().lower()
    ref = evidence_ref.strip()
    if not provider_name or not ref:
        raise MarketplaceCertificationEvidenceError(
            "provider and evidence_ref are required",
            code="VALIDATION_ERROR",
        )
    if env != "production":
        raise MarketplaceCertificationEvidenceError(
            "Production certification evidence must come from the production environment",
            code="NON_PRODUCTION_EVIDENCE",
        )

    profile = next(
        (item for item in config.runtime_profiles if item.provider == provider_name),
        None,
    )
    if profile is None:
        raise MarketplaceCertificationEvidenceError(
            f"Provider {provider_name!r} is not declared by this Outcome Pack",
            code="PROVIDER_NOT_DECLARED",
        )

    allowed = set(profile.actions)
    actions = sorted(
        {
            str(value).strip()
            for value in verified_actions
            if str(value).strip()
        }
    )
    undeclared = sorted(set(actions) - allowed)
    if undeclared:
        raise MarketplaceCertificationEvidenceError(
            "Evidence contains actions not declared by the runtime profile",
            code="UNDECLARED_ACTIONS",
        )
    if not actions:
        raise MarketplaceCertificationEvidenceError(
            "At least one verified action is required",
            code="VERIFIED_ACTIONS_REQUIRED",
        )

    row = {
        "asset_id": str(asset["id"]),
        "asset_version": _asset_version(asset),
        "org_id": asset.get("org_id"),
        "evidence_kind": "runtime",
        "provider": provider_name,
        "environment": env,
        "evidence_ref": ref,
        "verified_actions": actions,
        "verified_outcome_events": [],
        "metadata": metadata or {},
        "created_by": actor_id,
    }
    try:
        response = client.table("marketplace_certification_evidence").insert(row).execute()
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise MarketplaceCertificationEvidenceError(
                "This certification evidence reference has already been recorded",
                code="DUPLICATE_EVIDENCE",
            ) from exc
        raise
    stored = dict((response.data or [row])[0])
    report = certification_report_for_asset(client, asset)
    return {
        "evidence": stored,
        "certification": report.as_dict(),
    }
