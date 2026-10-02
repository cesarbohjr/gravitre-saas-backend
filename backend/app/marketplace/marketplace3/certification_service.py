"""Persisted Marketplace 3.0 certification and promotion lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.schemas import (
    OutcomePackAssetConfig,
    parse_asset_config,
    validate_asset_payload,
)


class Marketplace3CertificationError(Exception):
    code = "MARKETPLACE3_CERTIFICATION_ERROR"

    def __init__(self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.details = details or {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _asset_by_slug(client: Any, slug: str) -> dict[str, Any]:
    result = (
        client.table("marketplace_assets")
        .select("*")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        raise Marketplace3CertificationError(
            f"Marketplace asset not found: {slug}",
            code="NOT_FOUND",
        )
    return dict(rows[0])


def _sanitize_evidence(value: Any) -> Any:
    """Persist evidence references/metadata only; reject credential-shaped keys."""
    forbidden = {
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "password",
        "authorization",
        "cookie",
    }
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, nested in value.items():
            lowered = str(key).strip().lower()
            if lowered in forbidden or lowered.endswith("_secret") or lowered.endswith("_token") or lowered.endswith("_key"):
                raise Marketplace3CertificationError(
                    "Certification evidence must contain references/metadata only, not credentials.",
                    code="EVIDENCE_SECRET_FORBIDDEN",
                    details={"field": str(key)},
                )
            out[str(key)] = _sanitize_evidence(nested)
        return out
    if isinstance(value, list):
        return [_sanitize_evidence(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def certify_asset(
    client: Any,
    *,
    slug: str,
    actor_id: str,
    runtime_evidence: dict[str, Any] | None = None,
    outcome_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    asset = _asset_by_slug(client, slug)
    if asset.get("asset_type") != "outcome_pack":
        raise Marketplace3CertificationError(
            "Marketplace 3.0 certification is only available for outcome_pack assets.",
            code="UNSUPPORTED_ASSET_TYPE",
        )

    parsed = parse_asset_config("outcome_pack", asset.get("config") or {}, publish=False)
    if not isinstance(parsed, OutcomePackAssetConfig):
        raise Marketplace3CertificationError(
            "Outcome Pack config could not be parsed.",
            code="INVALID_CONFIG",
        )

    runtime = _sanitize_evidence(runtime_evidence or {})
    outcome = _sanitize_evidence(outcome_evidence or {})
    report = certify_outcome_pack(
        parsed,
        runtime_evidence=runtime,
        outcome_evidence=outcome,
    )
    report_payload = report.as_dict()
    evidence_payload = {
        "runtime": runtime,
        "outcome": outcome,
    }

    updated = (
        client.table("marketplace_assets")
        .update(
            {
                "certification_level": report.level,
                "certification_report": report_payload,
                "certification_evidence": evidence_payload,
                "certification_updated_at": _now(),
                "certified_by": actor_id,
            }
        )
        .eq("id", asset["id"])
        .execute()
    )
    row = dict((updated.data or [asset])[0])
    row.update(
        {
            "certification_level": report.level,
            "certification_report": report_payload,
            "certification_evidence": evidence_payload,
        }
    )
    return {
        "asset": row,
        "certification": report_payload,
    }


def promote_certified_asset(
    client: Any,
    *,
    slug: str,
    actor_id: str,
) -> dict[str, Any]:
    asset = _asset_by_slug(client, slug)
    if asset.get("asset_type") != "outcome_pack":
        raise Marketplace3CertificationError(
            "Only Marketplace 3.0 Outcome Packs can use certification promotion.",
            code="UNSUPPORTED_ASSET_TYPE",
        )

    persisted_evidence = (
        asset.get("certification_evidence")
        if isinstance(asset.get("certification_evidence"), dict)
        else {}
    )
    parsed = parse_asset_config("outcome_pack", asset.get("config") or {}, publish=False)
    if not isinstance(parsed, OutcomePackAssetConfig):
        raise Marketplace3CertificationError(
            "Outcome Pack config could not be parsed.",
            code="INVALID_CONFIG",
        )

    fresh_report = certify_outcome_pack(
        parsed,
        runtime_evidence=(
            persisted_evidence.get("runtime")
            if isinstance(persisted_evidence.get("runtime"), dict)
            else {}
        ),
        outcome_evidence=(
            persisted_evidence.get("outcome")
            if isinstance(persisted_evidence.get("outcome"), dict)
            else {}
        ),
    )
    level = fresh_report.level
    report = fresh_report.as_dict()
    if level not in {"production_verified", "outcome_verified"} or not fresh_report.publish_ready:
        raise Marketplace3CertificationError(
            "Outcome Pack is not evidence-linked production verified.",
            code="CERTIFICATION_REQUIRED",
            details={
                "certificationLevel": level or None,
                "publishReady": fresh_report.publish_ready,
                "findings": report.get("findings") or [],
            },
        )

    # Re-run component publish validation so evidence can never bypass current
    # Play bindings, agent requirements, dataset/dashboard structure, or
    # knowledge/capability contracts.
    for play in parsed.plays:
        validate_asset_payload(
            asset_type="play",
            config=play.model_dump(mode="json"),
            publish=True,
        )
    for agent in parsed.agents:
        validate_asset_payload(
            asset_type="ai_agent",
            config=agent.model_dump(mode="json"),
            publish=True,
        )
    validate_asset_payload(
        asset_type="dataset_pack",
        config=parsed.dataset.model_dump(mode="json"),
        publish=True,
    )
    validate_asset_payload(
        asset_type="dashboard_pack",
        config=parsed.dashboard.model_dump(mode="json"),
        publish=True,
    )

    tags = [str(tag) for tag in (asset.get("tags") or []) if str(tag).strip()]
    tags = [
        tag for tag in tags
        if tag not in {"production-verified", "outcome-verified"}
    ]
    tags.append("outcome-verified" if level == "outcome_verified" else "production-verified")

    now = _now()
    updated = (
        client.table("marketplace_assets")
        .update(
            {
                "visibility": "public",
                "status": "published",
                "verified": True,
                "tags": tags,
                "published_at": asset.get("published_at") or now,
                "updated_at": now,
                "certified_by": actor_id,
                "certification_level": level,
                "certification_report": report,
                "certification_updated_at": now,
            }
        )
        .eq("id", asset["id"])
        .execute()
    )
    row = dict((updated.data or [asset])[0])
    row.update(
        {
            "visibility": "public",
            "status": "published",
            "verified": True,
            "tags": tags,
            "certification_level": level,
            "certification_report": report,
        }
    )
    return {
        "promoted": True,
        "asset": row,
        "certification": report,
    }
