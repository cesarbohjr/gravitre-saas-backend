"""Apply selected improvements to one agent and confirm they landed (Model Studio).

Each improvement writes to the store the agent runtime already reads:

- instruction: ``custom_instructions`` row scoped by ``agent_id`` (injected by
  ``load_active_instruction_texts``). Operator-only agents cannot hold that FK, so
  the note is appended to ``operators.config.system_prompt`` instead (read by
  ``build_agent_system_prompt``).
- model: ``agents.model`` (same column the web PATCH route saves), or
  ``operators.config.model`` for operator-only agents (read by
  ``resolve_agent_record``).
- fine_tune: ``assign_trained_model_to_agent`` (agents.trained_model_id or
  operators.config.trained_model_id).
- knowledge: ``agent_knowledge_assignments`` row with ``source_type=rag_source``
  (used by retrieval scoring). Only agents with a public.agents row support this.

After applying, the agent's state is re-read and every applied step is checked
against it, so the caller sees what actually landed.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import HTTPException, status

from app.core.safe_dict import safe_normalize_stored_dict
from app.services.agent_finetune_service import (
    assign_trained_model_to_agent,
    load_operator_row,
)
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_AGENT_IMPROVEMENTS_APPLIED = "agent.improvements.applied"
RESOURCE_TYPE_AGENT = "agent"

DEFAULT_INSTRUCTION_NAME = "Model Studio note"
MAX_INSTRUCTION_CHARS = 4000
MAX_INSTRUCTION_NAME_CHARS = 120
MAX_KNOWLEDGE_SOURCES = 10
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")

StepKind = Literal["instruction", "model", "fine_tune", "knowledge"]
StepStatus = Literal["applied", "unchanged", "failed"]


@dataclass
class AgentTarget:
    agent_id: str
    storage: Literal["agent", "operator"]
    row: dict[str, Any]

    @property
    def config(self) -> dict[str, Any]:
        return safe_normalize_stored_dict(self.row, key="config")

    @property
    def name(self) -> str:
        return str(self.row.get("name") or "Agent")


@dataclass
class ImprovementStep:
    kind: StepKind
    status: StepStatus
    message: str
    target: str | None = None
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "message": self.message,
            "target": self.target,
            "verified": self.verified,
        }


@dataclass
class ImprovementRequest:
    instruction_content: str | None = None
    instruction_name: str | None = None
    model: str | None = None
    trained_model_id: str | None = None
    knowledge_source_ids: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            (self.instruction_content or "").strip()
            or (self.model or "").strip()
            or (self.trained_model_id or "").strip()
            or self.knowledge_source_ids
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("detail") or detail.get("error") or "Request failed")
        return str(detail or "Request failed")
    return "Could not save this change."


def load_agent_target(client: Any, org_id: str, agent_id: str) -> AgentTarget:
    """Resolve the org-scoped agent row, falling back to an operator-only row."""
    agent = (
        client.table("agents")
        .select("id, org_id, name, model, trained_model_id, config")
        .eq("id", agent_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if agent.data:
        return AgentTarget(agent_id=agent_id, storage="agent", row=dict(agent.data[0]))
    operator = load_operator_row(client, org_id, agent_id)
    if operator is not None:
        return AgentTarget(agent_id=agent_id, storage="operator", row=operator)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")


def _active_instruction_texts(client: Any, org_id: str, agent_id: str) -> list[dict[str, Any]]:
    try:
        rows = (
            client.table("custom_instructions")
            .select("id, name, content, is_active, updated_at")
            .eq("org_id", org_id)
            .eq("agent_id", agent_id)
            .eq("is_active", True)
            .execute()
        )
    except Exception:  # noqa: BLE001
        logger.debug("agent_improvement_instructions_read_failed agent_id=%s", agent_id, exc_info=True)
        return []
    return [dict(row) for row in rows.data or []]


def _knowledge_source_ids(client: Any, org_id: str, agent_id: str) -> list[str]:
    try:
        rows = (
            client.table("agent_knowledge_assignments")
            .select("source_id, source_type, enabled")
            .eq("org_id", org_id)
            .eq("agent_id", agent_id)
            .eq("source_type", "rag_source")
            .execute()
        )
    except Exception:  # noqa: BLE001
        logger.debug("agent_improvement_knowledge_read_failed agent_id=%s", agent_id, exc_info=True)
        return []
    return [
        str(row.get("source_id"))
        for row in rows.data or []
        if row.get("source_id") and row.get("enabled", True) is not False
    ]


def read_agent_improvement_state(client: Any, org_id: str, agent_id: str) -> dict[str, Any]:
    """Current runtime-relevant state for an agent, read from the stores runtime uses."""
    target = load_agent_target(client, org_id, agent_id)
    config = target.config
    if target.storage == "agent":
        model = str(target.row.get("model") or "").strip() or None
        trained = str(target.row.get("trained_model_id") or "").strip() or None
        instructions = [
            {"id": str(row.get("id") or ""), "name": row.get("name"), "content": str(row.get("content") or "")}
            for row in _active_instruction_texts(client, org_id, agent_id)
        ]
        knowledge = _knowledge_source_ids(client, org_id, agent_id)
    else:
        model = str(config.get("model") or "").strip() or None
        trained = str(config.get("trained_model_id") or "").strip() or None
        system_prompt = str(config.get("system_prompt") or config.get("systemPrompt") or "").strip()
        instructions = (
            [{"id": "config.system_prompt", "name": "Agent instructions", "content": system_prompt}]
            if system_prompt
            else []
        )
        knowledge = []
    return {
        "agentId": agent_id,
        "name": target.name,
        "storage": target.storage,
        "model": model,
        "trainedModelId": trained,
        "instructions": instructions,
        "knowledgeSourceIds": knowledge,
        "supportsKnowledge": target.storage == "agent",
    }


# ---------------------------------------------------------------------------
# Individual steps
# ---------------------------------------------------------------------------


def _apply_instruction(
    client: Any,
    target: AgentTarget,
    *,
    org_id: str,
    actor_id: str,
    content: str,
    name: str,
) -> ImprovementStep:
    if target.storage == "agent":
        existing = _active_instruction_texts(client, org_id, target.agent_id)
        if any(str(row.get("content") or "").strip() == content for row in existing):
            return ImprovementStep("instruction", "unchanged", "This note is already active.", target=name)
        inserted = (
            client.table("custom_instructions")
            .insert(
                {
                    "org_id": org_id,
                    "agent_id": target.agent_id,
                    "name": name,
                    "content": content,
                    "is_active": True,
                    "created_by": actor_id,
                }
            )
            .execute()
        )
        from app.services.training_service import invalidate_instruction_cache

        invalidate_instruction_cache(org_id)
        if not inserted.data:
            return ImprovementStep("instruction", "failed", "The note was not saved.", target=name)
        return ImprovementStep("instruction", "applied", "Note added.", target=name)

    config = target.config
    current = str(config.get("system_prompt") or config.get("systemPrompt") or "").strip()
    if content in current:
        return ImprovementStep("instruction", "unchanged", "This note is already active.", target=name)
    config["system_prompt"] = f"{current}\n\n{name}: {content}".strip() if current else f"{name}: {content}"
    config.pop("systemPrompt", None)
    updated = (
        client.table("operators")
        .update({"config": config, "updated_at": _now()})
        .eq("id", target.agent_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not updated.data:
        return ImprovementStep("instruction", "failed", "The note was not saved.", target=name)
    target.row["config"] = config
    return ImprovementStep("instruction", "applied", "Note added to the agent's instructions.", target=name)


def _apply_model(client: Any, target: AgentTarget, *, org_id: str, model: str) -> ImprovementStep:
    if model.lower() == "auto" or not _MODEL_ID_RE.match(model):
        return ImprovementStep("model", "failed", "Pick a specific model.", target=model)
    if target.storage == "agent":
        if str(target.row.get("model") or "").strip() == model:
            return ImprovementStep("model", "unchanged", "Already using this model.", target=model)
        updated = (
            client.table("agents")
            .update({"model": model, "updated_at": _now()})
            .eq("id", target.agent_id)
            .eq("org_id", org_id)
            .execute()
        )
        if not updated.data:
            return ImprovementStep("model", "failed", "The model was not saved.", target=model)
        target.row["model"] = model
        return ImprovementStep("model", "applied", "Model switched.", target=model)

    config = target.config
    if str(config.get("model") or "").strip() == model:
        return ImprovementStep("model", "unchanged", "Already using this model.", target=model)
    config["model"] = model
    updated = (
        client.table("operators")
        .update({"config": config, "updated_at": _now()})
        .eq("id", target.agent_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not updated.data:
        return ImprovementStep("model", "failed", "The model was not saved.", target=model)
    target.row["config"] = config
    return ImprovementStep("model", "applied", "Model switched.", target=model)


def _current_trained_model_id(target: AgentTarget) -> str | None:
    if target.storage == "agent":
        return str(target.row.get("trained_model_id") or "").strip() or None
    return str(target.config.get("trained_model_id") or "").strip() or None


def _apply_fine_tune(
    client: Any,
    target: AgentTarget,
    *,
    org_id: str,
    actor_id: str,
    trained_model_id: str,
) -> ImprovementStep:
    if _current_trained_model_id(target) == trained_model_id:
        return ImprovementStep("fine_tune", "unchanged", "This fine-tuned model is already attached.", target=trained_model_id)
    assign_trained_model_to_agent(
        client,
        org_id=org_id,
        agent_id=target.agent_id,
        trained_model_id=trained_model_id,
        actor_id=actor_id,
    )
    return ImprovementStep("fine_tune", "applied", "Fine-tuned model attached.", target=trained_model_id)


def _apply_knowledge_source(
    client: Any,
    target: AgentTarget,
    *,
    org_id: str,
    actor_id: str,
    source_id: str,
    already_assigned: set[str],
) -> ImprovementStep:
    if target.storage != "agent":
        return ImprovementStep(
            "knowledge",
            "failed",
            "Knowledge can't be attached to this agent from here. Open the agent to add it.",
            target=source_id,
        )
    if source_id in already_assigned:
        return ImprovementStep("knowledge", "unchanged", "Already attached.", target=source_id)
    source = (
        client.table("rag_sources")
        .select("id, name, title, org_id")
        .eq("id", source_id)
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not source.data:
        return ImprovementStep("knowledge", "failed", "Knowledge source not found.", target=source_id)
    row = source.data[0]
    label = str(row.get("name") or row.get("title") or "Knowledge source")

    from app.services.agent_knowledge_assignment_service import get_agent_knowledge_assignment_service

    get_agent_knowledge_assignment_service().create_assignment(
        client,
        org_id,
        target.agent_id,
        {
            "source_type": "rag_source",
            "source_id": source_id,
            "label": label,
            "enabled": True,
            "metadata": {"org_rag_source": True, "source": "model_studio"},
            "created_by": actor_id,
        },
    )
    already_assigned.add(source_id)
    return ImprovementStep("knowledge", "applied", f"Attached {label}.", target=source_id)


def _run_step(kind: StepKind, target_value: str | None, fn: Any) -> ImprovementStep:
    try:
        return fn()
    except HTTPException as exc:
        return ImprovementStep(kind, "failed", _error_message(exc), target=target_value)
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_improvement_step_failed kind=%s error=%s", kind, exc, exc_info=True)
        return ImprovementStep(kind, "failed", _error_message(exc), target=target_value)


def _verify(step: ImprovementStep, state: dict[str, Any], *, instruction_content: str | None) -> bool:
    if step.status == "failed":
        return False
    if step.kind == "model":
        return state.get("model") == step.target
    if step.kind == "fine_tune":
        return state.get("trainedModelId") == step.target
    if step.kind == "knowledge":
        return step.target in (state.get("knowledgeSourceIds") or [])
    if step.kind == "instruction" and instruction_content:
        return any(instruction_content in str(item.get("content") or "") for item in state.get("instructions") or [])
    return False


def apply_agent_improvements(
    client: Any,
    *,
    org_id: str,
    agent_id: str,
    actor_id: str,
    request: ImprovementRequest,
) -> dict[str, Any]:
    """Apply each selected improvement independently, then verify against stored state."""
    if request.is_empty():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose at least one improvement")

    target = load_agent_target(client, org_id, agent_id)
    steps: list[ImprovementStep] = []

    content = (request.instruction_content or "").strip()
    if content:
        name = (request.instruction_name or "").strip() or DEFAULT_INSTRUCTION_NAME
        if len(content) > MAX_INSTRUCTION_CHARS:
            steps.append(
                ImprovementStep("instruction", "failed", f"Keep the note under {MAX_INSTRUCTION_CHARS} characters.", target=name)
            )
        else:
            steps.append(
                _run_step(
                    "instruction",
                    name[:MAX_INSTRUCTION_NAME_CHARS],
                    lambda: _apply_instruction(
                        client,
                        target,
                        org_id=org_id,
                        actor_id=actor_id,
                        content=content,
                        name=name[:MAX_INSTRUCTION_NAME_CHARS],
                    ),
                )
            )

    model = (request.model or "").strip()
    if model:
        steps.append(_run_step("model", model, lambda: _apply_model(client, target, org_id=org_id, model=model)))

    trained_model_id = (request.trained_model_id or "").strip()
    if trained_model_id:
        steps.append(
            _run_step(
                "fine_tune",
                trained_model_id,
                lambda: _apply_fine_tune(
                    client, target, org_id=org_id, actor_id=actor_id, trained_model_id=trained_model_id
                ),
            )
        )

    source_ids = list(dict.fromkeys(str(s).strip() for s in request.knowledge_source_ids if str(s).strip()))
    if len(source_ids) > MAX_KNOWLEDGE_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Attach at most {MAX_KNOWLEDGE_SOURCES} knowledge sources at a time",
        )
    if source_ids:
        assigned = set(_knowledge_source_ids(client, org_id, agent_id)) if target.storage == "agent" else set()
        for source_id in source_ids:
            steps.append(
                _run_step(
                    "knowledge",
                    source_id,
                    lambda sid=source_id: _apply_knowledge_source(
                        client,
                        target,
                        org_id=org_id,
                        actor_id=actor_id,
                        source_id=sid,
                        already_assigned=assigned,
                    ),
                )
            )

    state = read_agent_improvement_state(client, org_id, agent_id)
    for step in steps:
        step.verified = _verify(step, state, instruction_content=content or None)

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_AGENT_IMPROVEMENTS_APPLIED,
        resource_type=RESOURCE_TYPE_AGENT,
        resource_id=agent_id,
        metadata={
            "source": "model_studio",
            "storage": target.storage,
            "steps": [
                {
                    "kind": s.kind,
                    "status": s.status,
                    "verified": s.verified,
                    # Instruction text stays out of audit metadata; it lives in custom_instructions.
                    "target": None if s.kind == "instruction" else s.target,
                }
                for s in steps
            ],
        },
    )

    return {
        "agentId": agent_id,
        "steps": [step.to_dict() for step in steps],
        "appliedCount": sum(1 for s in steps if s.status == "applied"),
        "failedCount": sum(1 for s in steps if s.status == "failed"),
        "state": state,
    }
