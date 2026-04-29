"""Training API: datasets, jobs, and custom instructions."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/training", tags=["training"])


class DatasetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., pattern="^(examples|documents|feedback)$")
    description: str | None = None


class DatasetRecordsRequest(BaseModel):
    records: list[dict]


class JobCreateRequest(BaseModel):
    dataset_id: str
    model_base: str


class InstructionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    agent_id: str | None = None


class InstructionUpdateRequest(BaseModel):
    name: str | None = None
    content: str | None = None
    agent_id: str | None = None
    is_active: bool | None = None


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    return "does not exist" in str(error).lower()


@router.get("/datasets")
async def list_datasets(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("training_datasets")
        .select("id, name, description, type, status, record_count, created_by, created_at, updated_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"datasets": []}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"datasets": list(response.data or [])}


@router.get("/datasets/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("training_datasets")
        .select("id, name, description, type, status, record_count, created_by, created_at, updated_at")
        .eq("org_id", org_id)
        .eq("id", dataset_id)
        .limit(1)
        .execute()
    )
    if _is_missing_table_error(response.error):
        raise HTTPException(status_code=404, detail="Dataset not found")
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    if not response.data:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dict(response.data[0])


@router.post("/datasets", status_code=status.HTTP_201_CREATED)
async def create_dataset(
    body: DatasetCreateRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("training_datasets")
        .insert(
            {
                "org_id": org_id,
                "name": body.name.strip(),
                "description": body.description,
                "type": body.type,
                "status": "processing",
                "record_count": 0,
                "created_by": user["user_id"],
            }
        )
        .select("id, name, description, type, status, record_count, created_by, created_at, updated_at")
        .limit(1)
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return dict((response.data or [{}])[0])


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("training_datasets")
        .delete()
        .eq("org_id", org_id)
        .eq("id", dataset_id)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"ok": True}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"ok": True}


@router.post("/datasets/{dataset_id}/records")
async def upload_dataset_records(
    dataset_id: str,
    body: DatasetRecordsRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    if not body.records:
        return {"added": 0}
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    rows = []
    for record in body.records:
        rows.append(
            {
                "org_id": org_id,
                "dataset_id": dataset_id,
                "input": str(record.get("input") or ""),
                "expected_output": str(record.get("expected_output") or ""),
                "metadata": record.get("metadata") or {},
                "created_by": user["user_id"],
            }
        )
    inserted = client.table("training_records").insert(rows).execute()
    if inserted.error:
        raise HTTPException(status_code=500, detail=str(inserted.error))

    update_dataset = (
        client.rpc(
            "increment_training_dataset_record_count",
            {"p_dataset_id": dataset_id, "p_org_id": org_id, "p_increment": len(rows)},
        )
        .execute()
    )
    if update_dataset.error and "function" in str(update_dataset.error).lower():
        # Fallback when RPC is not installed yet.
        dataset_resp = (
            client.table("training_datasets")
            .select("record_count")
            .eq("org_id", org_id)
            .eq("id", dataset_id)
            .limit(1)
            .execute()
        )
        current = int((dataset_resp.data or [{}])[0].get("record_count") or 0)
        client.table("training_datasets").update(
            {"record_count": current + len(rows), "status": "ready"}
        ).eq("org_id", org_id).eq("id", dataset_id).execute()
    return {"added": len(rows)}


@router.get("/jobs")
async def list_jobs(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("training_jobs")
        .select("id, dataset_id, model_base, status, progress, metrics, started_at, completed_at, error, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"jobs": []}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"jobs": list(response.data or [])}


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("training_jobs")
        .select("id, dataset_id, model_base, status, progress, metrics, started_at, completed_at, error, created_at")
        .eq("org_id", org_id)
        .eq("id", job_id)
        .limit(1)
        .execute()
    )
    if _is_missing_table_error(response.error):
        raise HTTPException(status_code=404, detail="Job not found")
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    if not response.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(response.data[0])


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    body: JobCreateRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("training_jobs")
        .insert(
            {
                "org_id": org_id,
                "dataset_id": body.dataset_id,
                "model_base": body.model_base,
                "status": "queued",
                "progress": 0,
                "metrics": {},
                "created_by": user["user_id"],
            }
        )
        .select("id, dataset_id, model_base, status, progress, metrics, started_at, completed_at, error, created_at")
        .limit(1)
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return dict((response.data or [{}])[0])


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("training_jobs")
        .update({"status": "failed", "error": "Cancelled by user"})
        .eq("org_id", org_id)
        .eq("id", job_id)
        .select("id, dataset_id, model_base, status, progress, metrics, started_at, completed_at, error, created_at")
        .limit(1)
        .execute()
    )
    if _is_missing_table_error(response.error):
        raise HTTPException(status_code=404, detail="Job not found")
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    if not response.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(response.data[0])


@router.get("/instructions")
async def list_instructions(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("custom_instructions")
        .select("id, agent_id, name, content, is_active, created_at, updated_at")
        .eq("org_id", org_id)
        .order("updated_at", desc=True)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"instructions": []}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"instructions": list(response.data or [])}


@router.get("/instructions/{instruction_id}")
async def get_instruction(
    instruction_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("custom_instructions")
        .select("id, agent_id, name, content, is_active, created_at, updated_at")
        .eq("org_id", org_id)
        .eq("id", instruction_id)
        .limit(1)
        .execute()
    )
    if _is_missing_table_error(response.error):
        raise HTTPException(status_code=404, detail="Instruction not found")
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    if not response.data:
        raise HTTPException(status_code=404, detail="Instruction not found")
    return dict(response.data[0])


@router.post("/instructions", status_code=status.HTTP_201_CREATED)
async def create_instruction(
    body: InstructionCreateRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("custom_instructions")
        .insert(
            {
                "org_id": org_id,
                "agent_id": body.agent_id,
                "name": body.name.strip(),
                "content": body.content,
                "is_active": True,
                "created_by": user["user_id"],
            }
        )
        .select("id, agent_id, name, content, is_active, created_at, updated_at")
        .limit(1)
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return dict((response.data or [{}])[0])


@router.patch("/instructions/{instruction_id}")
async def update_instruction(
    instruction_id: str,
    body: InstructionUpdateRequest,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=400, detail="No updates provided")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("custom_instructions")
        .update(payload)
        .eq("org_id", org_id)
        .eq("id", instruction_id)
        .select("id, agent_id, name, content, is_active, created_at, updated_at")
        .limit(1)
        .execute()
    )
    if _is_missing_table_error(response.error):
        raise HTTPException(status_code=404, detail="Instruction not found")
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    if not response.data:
        raise HTTPException(status_code=404, detail="Instruction not found")
    return dict(response.data[0])


@router.delete("/instructions/{instruction_id}")
async def delete_instruction(
    instruction_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("custom_instructions")
        .delete()
        .eq("org_id", org_id)
        .eq("id", instruction_id)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"ok": True}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"ok": True}
