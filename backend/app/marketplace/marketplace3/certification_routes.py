"""Organization-admin certification controls; requests cannot supply proof."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from supabase import create_client

from app.auth.dependencies import require_admin
from app.config import Settings, get_settings
from app.core.io_pool import run_io
from app.core.db import shared_service_client
from app.marketplace.crud import _fetch_asset, MarketplaceCrudError
from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.certification_store import (
    OutcomePackCertificationError, certify_and_record_outcome_pack, get_outcome_pack_certification,
    assert_outcome_pack_publish_ready,
)
from app.marketplace.schemas import OutcomePackAssetConfig

router = APIRouter()


class CertificationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["fixture", "production"] = "fixture"


def _owned_pack(client, org_id: str, asset_ref: str):
    try:
        asset = _fetch_asset(client, asset_ref)
    except MarketplaceCrudError as exc:
        raise HTTPException(404, "Outcome Pack not found") from exc
    if str(asset.get("org_id") or "") != org_id or asset.get("asset_type") != "outcome_pack":
        raise HTTPException(404, "Outcome Pack not found")
    try:
        OutcomePackAssetConfig.model_validate(asset.get("config"))
    except ValueError as exc:
        raise HTTPException(409, "Complete the Outcome Pack configuration before certification") from exc
    return asset


@router.get("/assets/{asset_ref}/certification")
def certification_status(asset_ref: str, admin: Annotated[tuple, Depends(require_admin)],
                         settings: Annotated[Settings, Depends(get_settings)]):
    _, org_id = admin
    client = shared_service_client(settings, create_client)
    asset = _owned_pack(client, org_id, asset_ref)
    certificate = get_outcome_pack_certification(client, org_id=org_id, asset_id=str(asset["id"]), config=asset["config"])
    if certificate and certificate["publishReady"]:
        try:
            certificate = assert_outcome_pack_publish_ready(client, org_id=org_id, asset_id=str(asset["id"]), config=asset["config"])
        except OutcomePackCertificationError as exc:
            certificate = {**certificate, "publishReady": False, "report": {
                **certificate.get("report", {}), "findings": [
                    *certificate.get("report", {}).get("findings", []),
                    {"code": exc.code, "message": str(exc)},
                ],
            }}
    return {"assetId": str(asset["id"]), "certification": certificate, "publishReady": bool(certificate and certificate["publishReady"])}


@router.post("/assets/{asset_ref}/certification/run")
async def run_certification(asset_ref: str, body: CertificationRunRequest, request: Request,
                      admin: Annotated[tuple, Depends(require_admin)],
                      settings: Annotated[Settings, Depends(get_settings)]):
    user, org_id = admin
    client = shared_service_client(settings, create_client)
    asset = await run_io(_owned_pack, client, org_id, asset_ref)
    if body.mode == "fixture":
        report = certify_outcome_pack(OutcomePackAssetConfig.model_validate(asset["config"]))
        return {"assetId": str(asset["id"]), "mode": "fixture", "publishReady": False,
                "evidenceLevel": "configuration_contract_only", "report": report.as_dict()}
    from app.marketplace.marketplace3.scenario_runner import record_executed_scenarios
    authorization = request.headers.get("authorization", "")
    access_token = authorization[7:] if authorization.lower().startswith("bearer ") else ""
    scenarios = await record_executed_scenarios(client, settings, org_id=org_id, asset=asset,
        config=OutcomePackAssetConfig.model_validate(asset["config"]), access_token=access_token)
    try:
        result = await run_io(certify_and_record_outcome_pack, client, org_id=org_id, asset_id=str(asset["id"]),
            config=asset["config"], actor_id=str(user["user_id"]))
        return {**result, "scenarios": scenarios}
    except OutcomePackCertificationError as exc:
        raise HTTPException(409, {"code": exc.code, "message": str(exc)}) from exc


@router.post("/assets/{asset_ref}/certification/install")
def prepare_certification_install(asset_ref: str, admin: Annotated[tuple, Depends(require_admin)],
                                  settings: Annotated[Settings, Depends(get_settings)]):
    """Materialize owned internal draft primitives in OBSERVE mode; never publish."""
    from app.marketplace.service import _install_outcome_pack, _check_plan_limits, _find_active_connector_id, MarketplaceError
    from app.marketplace.marketplace3.certification_store import outcome_pack_config_digest
    user, org_id = admin
    client = shared_service_client(settings, create_client)
    asset = _owned_pack(client, org_id, asset_ref)
    if asset.get("visibility") not in {"private", "internal"} or asset.get("status") not in {"draft", "pending_review"}:
        raise HTTPException(409, "Certification preparation requires an owned private or internal draft")
    config = OutcomePackAssetConfig.model_validate(asset["config"])
    _check_plan_limits(client, org_id, "outcome_pack")
    providers = {profile.provider for profile in config.runtime_profiles}
    connectors = {provider: _find_active_connector_id(client, org_id, provider, environment_name="production") for provider in providers}
    if any(value is None for value in connectors.values()):
        raise HTTPException(409, "Connect required apps before preparing the certification installation")
    try:
        result = _install_outcome_pack(client, org_id, asset, config, actor_id=str(user["user_id"]),
            environment_name="production", connector_ids=connectors)
    except MarketplaceError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"assetId": str(asset["id"]), "configDigest": outcome_pack_config_digest(config),
            "operatingMode": "OBSERVE", "publishReady": False, "installation": result}


@router.get("/outcome-pack-blueprints")
def list_outcome_pack_blueprints(admin: Annotated[tuple, Depends(require_admin)]):
    from app.outcome_packs.registry import list_packs
    return {"blueprints": [{"id": pack.pack_id, "title": pack.title, "department": pack.department,
        "playCount": len(pack.config.plays), "agentCount": len(pack.config.agents),
        "skillPackages": sorted(set(pack.config.skill_bindings.values())),
        "status": "blueprint", "publishReady": False} for pack in list_packs()]}


@router.post("/outcome-pack-blueprints/{pack_id}/draft")
def create_blueprint_draft(pack_id: str, admin: Annotated[tuple, Depends(require_admin)],
                           settings: Annotated[Settings, Depends(get_settings)]):
    from app.outcome_packs.registry import get_pack
    from app.marketplace.crud import create_org_asset, _serialize_asset
    pack = get_pack(pack_id)
    if pack is None:
        raise HTTPException(404, "Outcome Pack blueprint not found")
    user, org_id = admin
    client = shared_service_client(settings, create_client)
    slug = f"{pack.slug}-{org_id}"
    rows = (client.table("marketplace_assets").select("*").eq("org_id", org_id).eq("slug", slug).limit(1).execute().data or [])
    if rows:
        existing = rows[0]
        if existing.get("org_id") != org_id or existing.get("asset_type") != "outcome_pack":
            raise HTTPException(409, "Blueprint draft identity conflicts with an existing asset")
        if existing.get("status") not in {"draft", "pending_review"}:
            raise HTTPException(409, "The workspace copy is already published or archived; use its normal lifecycle controls")
        return {"asset": _serialize_asset(existing), "created": False}
    try:
        created = create_org_asset(client, org_id, actor_id=str(user["user_id"]), slug=slug,
            title=pack.title, description=pack.config.outcome_contract.problem,
            asset_type="outcome_pack", category="outcome_pack", department=pack.department,
            config=pack.config.model_dump(mode="json"), business_outcome=pack.config.outcome_contract.target_outcome,
            required_connectors=[{"connectorType": profile.provider, "label": profile.provider, "required": True,
                                  "connectPath": f"/connectors?type={profile.provider}"} for profile in pack.config.runtime_profiles])
    except MarketplaceCrudError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"asset": created.get("asset", created), "created": True}
