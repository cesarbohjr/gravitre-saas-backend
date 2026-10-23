"""Persistence and publish gating for Marketplace 3.0 Outcome Pack certification."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.schemas import OutcomePackAssetConfig


class OutcomePackCertificationError(Exception):
    code = "OUTCOME_PACK_CERTIFICATION_REQUIRED"

    def __init__(self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.details = details or {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def outcome_pack_config_digest(config: dict[str, Any] | OutcomePackAssetConfig) -> str:
    payload = config.model_dump(mode="json") if isinstance(config, OutcomePackAssetConfig) else config
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def certify_and_record_outcome_pack(
    client: Any,
    *,
    org_id: str,
    asset_id: str,
    config: dict[str, Any] | OutcomePackAssetConfig,
    actor_id: str,
    resolved_skill_ids: set[str] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = config if isinstance(config, OutcomePackAssetConfig) else OutcomePackAssetConfig.model_validate(config)
    report = certify_outcome_pack(
        parsed,
        resolved_skill_ids=resolved_skill_ids,
        outcome_evidence=evidence or {},
    )
    digest = outcome_pack_config_digest(parsed)
    row = {
        "org_id": org_id,
        "asset_id": asset_id,
        "config_digest": digest,
        "certification_level": report.level,
        "publish_ready": report.publish_ready,
        "report": report.as_dict(),
        "evidence": evidence or {},
        "certified_by": actor_id,
        "certified_at": _now(),
        "updated_at": _now(),
    }
    result = (
        client.table("marketplace_outcome_pack_certifications")
        .upsert(row, on_conflict="asset_id,config_digest")
        .execute()
    )
    stored = dict((result.data or [row])[0])
    return {
        "id": stored.get("id"),
        "assetId": asset_id,
        "configDigest": digest,
        "level": report.level,
        "publishReady": report.publish_ready,
        "report": report.as_dict(),
        "evidence": evidence or {},
        "certifiedAt": stored.get("certified_at") or row["certified_at"],
    }


def get_outcome_pack_certification(
    client: Any,
    *,
    org_id: str,
    asset_id: str,
    config: dict[str, Any] | OutcomePackAssetConfig,
) -> dict[str, Any] | None:
    digest = outcome_pack_config_digest(config)
    result = (
        client.table("marketplace_outcome_pack_certifications")
        .select("*")
        .eq("org_id", org_id)
        .eq("asset_id", asset_id)
        .eq("config_digest", digest)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return None
    row = dict(rows[0])
    return {
        "id": row.get("id"),
        "assetId": asset_id,
        "configDigest": digest,
        "level": row.get("certification_level"),
        "publishReady": bool(row.get("publish_ready")),
        "report": row.get("report") if isinstance(row.get("report"), dict) else {},
        "evidence": row.get("evidence") if isinstance(row.get("evidence"), dict) else {},
        "certifiedAt": row.get("certified_at"),
    }


def assert_outcome_pack_publish_ready(
    client: Any,
    *,
    org_id: str,
    asset_id: str,
    config: dict[str, Any] | OutcomePackAssetConfig,
) -> dict[str, Any]:
    certification = get_outcome_pack_certification(
        client,
        org_id=org_id,
        asset_id=asset_id,
        config=config,
    )
    if certification is None:
        raise OutcomePackCertificationError(
            "Marketplace 3.0 Outcome Pack must be certified against its current configuration before publication.",
            details={"assetId": asset_id, "reason": "certification_missing"},
        )
    if not certification["publishReady"] or certification["level"] not in {
        "production_verified",
        "outcome_verified",
    }:
        raise OutcomePackCertificationError(
            "Marketplace 3.0 Outcome Pack has not reached Production Verified certification.",
            details={
                "assetId": asset_id,
                "reason": "certification_not_publish_ready",
                "level": certification["level"],
                "report": certification["report"],
            },
        )
    return certification
