"""Assign fine-tuned models to agents and resolve inference with fallback (STA-99)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel

from app.core.errors import error_detail
from app.services.model_router import ModelResponse, ModelRouter, TaskType
from app.services.providers.base import AllProvidersFailedError, ProviderInvalidResponseError
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

RESOURCE_TYPE_AGENT = "agent"
AUDIT_AGENT_MODEL_ASSIGNED = "agent.finetuned_model.assigned"
AUDIT_AGENT_MODEL_INFERENCE = "agent.model.inference"

DEFAULT_AGENT_BASE_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class AgentInferenceModel:
    agent_id: str
    base_model: str
    trained_model_id: str | None
    trained_model_version: int | None
    fine_tuned_openai_id: str | None


def _extract_fine_tuned_openai_id(metrics: dict[str, Any] | None) -> str | None:
    if not metrics:
        return None
    custom = metrics.get("custom_metrics") if isinstance(metrics.get("custom_metrics"), dict) else {}
    value = custom.get("fine_tuned_model") or metrics.get("fine_tuned_model")
    return str(value).strip() if value else None


def resolve_agent_inference_model(client: Any, org_id: str, agent: dict[str, Any]) -> AgentInferenceModel:
    """Resolve base and optional fine-tuned OpenAI model for an agent."""
    agent_id = str(agent["id"])
    base_model = (agent.get("model") or "").strip() or DEFAULT_AGENT_BASE_MODEL
    trained_model_id = agent.get("trained_model_id")
    if not trained_model_id:
        return AgentInferenceModel(
            agent_id=agent_id,
            base_model=base_model,
            trained_model_id=None,
            trained_model_version=None,
            fine_tuned_openai_id=None,
        )

    model_row = (
        client.table("trained_models")
        .select("id, org_id, model_type, status, base_model, deployed_version, current_version")
        .eq("id", str(trained_model_id))
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not model_row.data:
        return AgentInferenceModel(
            agent_id=agent_id,
            base_model=base_model,
            trained_model_id=str(trained_model_id),
            trained_model_version=None,
            fine_tuned_openai_id=None,
        )

    row = model_row.data[0]
    if row.get("model_type") != "fine_tuned_llm":
        return AgentInferenceModel(
            agent_id=agent_id,
            base_model=base_model,
            trained_model_id=str(trained_model_id),
            trained_model_version=None,
            fine_tuned_openai_id=None,
        )

    version = row.get("deployed_version") or row.get("current_version")
    if not version:
        return AgentInferenceModel(
            agent_id=agent_id,
            base_model=(row.get("base_model") or base_model),
            trained_model_id=str(trained_model_id),
            trained_model_version=None,
            fine_tuned_openai_id=None,
        )

    version_row = (
        client.table("model_versions")
        .select("metrics")
        .eq("model_id", str(trained_model_id))
        .eq("version", int(version))
        .limit(1)
        .execute()
    )
    metrics = version_row.data[0].get("metrics") if version_row.data else {}
    ft_id = _extract_fine_tuned_openai_id(metrics if isinstance(metrics, dict) else None)
    return AgentInferenceModel(
        agent_id=agent_id,
        base_model=(row.get("base_model") or base_model),
        trained_model_id=str(trained_model_id),
        trained_model_version=int(version),
        fine_tuned_openai_id=ft_id,
    )


def assign_trained_model_to_agent(
    client: Any,
    *,
    org_id: str,
    agent_id: str,
    trained_model_id: str | None,
    actor_id: str,
) -> dict[str, Any]:
    """Assign or clear a fine-tuned model on an agent."""
    agent = (
        client.table("agents")
        .select("id, org_id, name, trained_model_id")
        .eq("id", agent_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not agent.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if trained_model_id:
        model = (
            client.table("trained_models")
            .select("id, org_id, model_type, status, name")
            .eq("id", trained_model_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        if not model.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_detail("Trained model not found", "MODEL_NOT_FOUND"),
            )
        row = model.data[0]
        if row.get("model_type") != "fine_tuned_llm":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail("Only fine_tuned_llm models can be assigned to agents", "INVALID_MODEL_TYPE"),
            )
        if row.get("status") not in {"ready", "deployed"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail("Model must be ready or deployed before assignment", "MODEL_NOT_READY"),
            )

    updated = (
        client.table("agents")
        .update(
            {
                "trained_model_id": trained_model_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", agent_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Agent update failed")

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_AGENT_MODEL_ASSIGNED,
        resource_type=RESOURCE_TYPE_AGENT,
        resource_id=agent_id,
        metadata={"trainedModelId": trained_model_id},
    )
    return dict(updated.data[0])


def list_deployable_fine_tuned_models(client: Any, org_id: str) -> list[dict[str, Any]]:
    """List org fine-tuned LLM models available for agent assignment."""
    result = (
        client.table("trained_models")
        .select("id, name, status, base_model, deployed_version, current_version, dataset_id, created_at")
        .eq("org_id", org_id)
        .eq("model_type", "fine_tuned_llm")
        .in_("status", ["ready", "deployed"])
        .order("created_at", desc=True)
        .execute()
    )
    models: list[dict[str, Any]] = []
    for row in result.data or []:
        version = row.get("deployed_version") or row.get("current_version")
        ft_id = None
        if version:
            version_row = (
                client.table("model_versions")
                .select("metrics")
                .eq("model_id", row["id"])
                .eq("version", int(version))
                .limit(1)
                .execute()
            )
            if version_row.data:
                metrics = version_row.data[0].get("metrics")
                ft_id = _extract_fine_tuned_openai_id(metrics if isinstance(metrics, dict) else None)
        models.append(
            {
                "id": str(row["id"]),
                "name": row.get("name"),
                "status": row.get("status"),
                "baseModel": row.get("base_model"),
                "deployedVersion": row.get("deployed_version"),
                "currentVersion": row.get("current_version"),
                "fineTunedOpenAiId": ft_id,
                "datasetId": str(row["dataset_id"]) if row.get("dataset_id") else None,
                "createdAt": row.get("created_at"),
            }
        )
    return models


async def complete_for_agent(
    router: ModelRouter,
    *,
    task_type: TaskType,
    prompt: str,
    system_prompt: str | None,
    response_format: type[BaseModel] | None,
    org_id: str,
    agent: dict[str, Any],
    client: Any,
    actor_id: str | None = None,
    run_id: str | None = None,
) -> ModelResponse:
    """Run model completion for an agent, preferring fine-tuned model with base fallback."""
    inference = resolve_agent_inference_model(client, org_id, agent)
    used_fallback = False
    model_used = inference.fine_tuned_openai_id or inference.base_model

    async def _call(model_override: str | None, fallback: bool) -> ModelResponse:
        return await router.complete(
            task_type=task_type,
            prompt=prompt,
            system_prompt=system_prompt,
            response_format=response_format,
            org_id=org_id,
            model_override=model_override,
            agent_id=inference.agent_id,
            trained_model_id=inference.trained_model_id,
            trained_model_version=inference.trained_model_version,
            used_fallback=fallback,
        )

    try:
        if inference.fine_tuned_openai_id:
            response = await _call(inference.fine_tuned_openai_id, False)
        else:
            response = await _call(None, False)
    except (AllProvidersFailedError, ProviderInvalidResponseError, ValueError) as exc:
        if not inference.fine_tuned_openai_id:
            raise
        logger.warning(
            "agent_finetune_fallback agent_id=%s model=%s error=%s",
            inference.agent_id,
            inference.fine_tuned_openai_id,
            str(exc),
        )
        used_fallback = True
        model_used = inference.base_model
        response = await _call(inference.base_model, True)

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id or org_id,
        action=AUDIT_AGENT_MODEL_INFERENCE,
        resource_type=RESOURCE_TYPE_AGENT,
        resource_id=inference.agent_id,
        metadata={
            "runId": run_id,
            "trainedModelId": inference.trained_model_id,
            "trainedModelVersion": inference.trained_model_version,
            "modelUsed": response.model,
            "provider": response.provider,
            "usedFallback": used_fallback,
            "taskType": task_type.value,
            "modelCallId": response.model_call_id,
        },
    )
    return response
