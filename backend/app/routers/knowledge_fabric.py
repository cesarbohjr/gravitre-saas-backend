"""Platform knowledge fabric API — packs, retrieve, admin ingest."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.knowledge_fabric.ingest import ingest_pack, register_all_sources
from app.knowledge_fabric.registry import list_platform_packs
from app.knowledge_fabric.retrieval import retrieve_knowledge_fabric
from app.knowledge_fabric.router import classify_knowledge_query

router = APIRouter(prefix="/api/knowledge-fabric", tags=["knowledge-fabric"])


def _client(settings: Settings):
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=2)
    assigned_pack_ids: list[str] = Field(default_factory=list)
    agent_department: str | None = None
    top_k: int = Field(default=6, ge=1, le=20)
    allow_live_internet: bool = False


class IngestRequest(BaseModel):
    pack_id: str
    limit: int = Field(default=5, ge=1, le=20)
    embed: bool = True


@router.get("/packs")
async def list_packs(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, Any]:
    _ = current_user
    return {"packs": list_platform_packs()}


@router.post("/classify")
async def classify_query(
    body: RetrieveRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, Any]:
    _ = current_user
    route = classify_knowledge_query(
        body.query,
        assigned_pack_ids=body.assigned_pack_ids,
        agent_department=body.agent_department,
        allow_live_internet=body.allow_live_internet,
    )
    return {"route": route.to_dict()}


@router.post("/retrieve")
async def retrieve(
    body: RetrieveRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ = current_user
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    # Platform shared retrieval — never reads rag_* for this path
    result = retrieve_knowledge_fabric(
        client,
        body.query,
        assigned_pack_ids=body.assigned_pack_ids,
        agent_department=body.agent_department,
        top_k=body.top_k,
        settings=settings,
    )
    result["org_id"] = org_id
    result["isolation"] = {
        "namespace": "platform_shared",
        "customer_rag_tables_touched": False,
    }
    return result


@router.post("/admin/register-sources", status_code=status.HTTP_201_CREATED)
async def admin_register_sources(
    _: Annotated[dict, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    client = _client(settings)
    rows = register_all_sources(client)
    return {"registered": len(rows), "source_ids": [r.get("source_id") for r in rows]}


@router.post("/admin/ingest")
async def admin_ingest(
    body: IngestRequest,
    _: Annotated[dict, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if body.pack_id in {"pack.sales", "pack.marketing"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Sales/Marketing packs are HOLD — choose commercially licensed content (C) "
                "or originally-authored Gravitre content before ingest."
            ),
        )
    client = _client(settings)
    register_all_sources(client)
    return await ingest_pack(
        client,
        body.pack_id,
        settings=settings,
        embed=body.embed,
        limit=body.limit,
    )
