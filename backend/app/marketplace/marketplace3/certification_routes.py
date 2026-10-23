"""Organization-admin certification controls; requests cannot supply proof."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from supabase import create_client

from app.auth.dependencies import require_admin
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.marketplace.crud import _fetch_asset, MarketplaceCrudError
from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.certification_store import (
    OutcomePackCertificationError, certify_and_record_outcome_pack, get_outcome_pack_certification,
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
    return asset


@router.get("/assets/{asset_ref}/certification")
def certification_status(asset_ref: str, admin: Annotated[tuple, Depends(require_admin)],
                         settings: Annotated[Settings, Depends(get_settings)]):
    _, org_id = admin
    client = shared_service_client(settings, create_client)
    asset = _owned_pack(client, org_id, asset_ref)
    certificate = get_outcome_pack_certification(client, org_id=org_id, asset_id=str(asset["id"]), config=asset["config"])
    return {"assetId": str(asset["id"]), "certification": certificate, "publishReady": bool(certificate and certificate["publishReady"])}


@router.post("/assets/{asset_ref}/certification/run")
def run_certification(asset_ref: str, body: CertificationRunRequest,
                      admin: Annotated[tuple, Depends(require_admin)],
                      settings: Annotated[Settings, Depends(get_settings)]):
    user, org_id = admin
    client = shared_service_client(settings, create_client)
    asset = _owned_pack(client, org_id, asset_ref)
    if body.mode == "fixture":
        report = certify_outcome_pack(OutcomePackAssetConfig.model_validate(asset["config"]))
        return {"assetId": str(asset["id"]), "mode": "fixture", "publishReady": False,
                "evidenceLevel": "configuration_contract_only", "report": report.as_dict()}
    try:
        return certify_and_record_outcome_pack(client, org_id=org_id, asset_id=str(asset["id"]),
            config=asset["config"], actor_id=str(user["user_id"]))
    except OutcomePackCertificationError as exc:
        raise HTTPException(409, {"code": exc.code, "message": str(exc)}) from exc
