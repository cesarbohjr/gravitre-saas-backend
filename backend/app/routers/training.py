"""Training API: datasets, jobs, and custom instructions."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.core.supabase_response import response_error
from app.services.agent_finetune_service import assign_trained_model_to_agent, list_deployable_fine_tuned_models
from app.services.handoff_service import get_agent
from app.services.training_service import (
    is_schema_unavailable_error,
    list_custom_instructions,
    list_training_datasets,
    list_training_jobs,
    list_workflow_agents,
)
from app.workers.queue import enqueue_training_job

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


class AgentFineTunedModelRequest(BaseModel):
    trained_model_id: str | None = Field(default=None, alias="trainedModelId")

    model_config = {"populate_by_name": True}


def _is_missing_table_error(error: Exception | None) -> bool:
    return is_schema_unavailable_error(error)


def _raise_if_response_error(response: Any, *, not_found: str | None = None) -> None:
    error = response_error(response)
    if error and _is_missing_table_error(error):
        if not_found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Training storage is not provisioned. Apply database migrations.",
        )
    if error:
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/datasets")
async def list_datasets(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return {"datasets": list_training_datasets(client, org_id)}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
    if _is_missing_table_error(response_error(response)):
        raise HTTPException(status_code=404, detail="Dataset not found")
    _raise_if_response_error(response)
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
    _raise_if_response_error(response)
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
    if _is_missing_table_error(response_error(response)):
        return {"ok": True}
    _raise_if_response_error(response)
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
    inserted_error = response_error(inserted)
    if inserted_error:
        if _is_missing_table_error(inserted_error):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Training storage is not provisioned. Apply database migrations.",
            )
        raise HTTPException(status_code=500, detail=str(inserted_error))

    update_dataset = (
        client.rpc(
            "increment_training_dataset_record_count",
            {"p_dataset_id": dataset_id, "p_org_id": org_id, "p_increment": len(rows)},
        )
        .execute()
    )
    update_error = response_error(update_dataset)
    if update_error and "function" in str(update_error).lower():
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
    try:
        return {"jobs": list_training_jobs(client, org_id)}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
    if _is_missing_table_error(response_error(response)):
        raise HTTPException(status_code=404, detail="Job not found")
    _raise_if_response_error(response)
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
    _raise_if_response_error(response)
    job = dict((response.data or [{}])[0])
    job_id = str(job.get("id") or "")
    if job_id:
        await enqueue_training_job(job_id)
    return job


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
    if _is_missing_table_error(response_error(response)):
        raise HTTPException(status_code=404, detail="Job not found")
    _raise_if_response_error(response)
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
    try:
        return {"instructions": list_custom_instructions(client, org_id)}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
    if _is_missing_table_error(response_error(response)):
        raise HTTPException(status_code=404, detail="Instruction not found")
    _raise_if_response_error(response)
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
    _raise_if_response_error(response)
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
    if _is_missing_table_error(response_error(response)):
        raise HTTPException(status_code=404, detail="Instruction not found")
    _raise_if_response_error(response)
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
    if _is_missing_table_error(response_error(response)):
        return {"ok": True}
    _raise_if_response_error(response)
    return {"ok": True}


@router.get("/workflow-agents")
async def list_workflow_agents(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Workflow agents from agents table (STA-99 assignment targets)."""
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return {"agents": list_workflow_agents(client, org_id)}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/fine-tuned-models")
async def list_fine_tuned_models_for_agents(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """List deployable fine-tuned LLM models (STA-99)."""
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return {"models": list_deployable_fine_tuned_models(client, org_id)}
    except Exception as exc:  # noqa: BLE001
        if is_schema_unavailable_error(exc):
            return {"models": []}
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/agents/{agent_id}/fine-tuned-model")
async def get_agent_fine_tuned_model_assignment(
    agent_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    agent = get_agent(client, org_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "agentId": agent_id,
        "trainedModelId": agent.get("trained_model_id"),
        "baseModel": agent.get("model"),
    }


@router.put("/agents/{agent_id}/fine-tuned-model")
async def assign_agent_fine_tuned_model(
    agent_id: str,
    body: AgentFineTunedModelRequest,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin_ctx
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    agent = assign_trained_model_to_agent(
        client,
        org_id=org_id,
        agent_id=agent_id,
        trained_model_id=body.trained_model_id,
        actor_id=user["user_id"],
    )
    return {"agentId": agent_id, "trainedModelId": agent.get("trained_model_id")}
