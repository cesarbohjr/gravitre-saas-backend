"""Multi-connector chat orchestration with plan confirm and step-by-step approval."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, replace
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.artifact_registry_service import serialize_execution_result
from app.services.chat_action_mapper import get_chat_action_mapper
from app.services.chat_connector_models import INTEGRATION_ALIASES, ConnectorActionPlan
from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    get_chat_connector_execution_service,
)
from app.services.connector_execution_matrix import skip_reason_for_entry
from app.services.conversation_state_service import get_conversation_state_service
from app.services.conversational_execution_service import (
    CONFIRM_PATTERN,
    DECLINE_PATTERN,
    ExecutionResult,
)
from app.services.notification_emitter import emit_notification
from app.services.chat_orchestration_runs import (
    finalize_orchestration_run,
    resolve_orchestration_result_url,
    start_orchestration_run,
    sync_orchestration_step,
)
from app.services.connector_session_state import (
    bind_plan_from_session,
    build_session_summary,
    connector_session_patch,
    load_connector_session,
    record_entity_from_execution,
    record_step_output,
    sync_legacy_resolved_entities,
)

logger = get_logger(__name__)

MULTI_STEP_SPLIT = re.compile(
    r"(?:,\s+and\s+|\s+;\s+|\s+then\s+|\s+and then\s+|"
    r"\s+and\s+(?=notify|create|post|send|update|add|log|draft|search|find|look|query|message)\b)",
    re.I,
)
SEGMENT_COMMA = re.compile(
    r",\s*(?=(?:create|build|make|post|send|notify|update|add|log|draft|search|find)\b)",
    re.I,
)
MULTI_STEP_HINT = re.compile(
    r"\b(then|and then|after that|followed by|next,|also notify|and notify)\b",
    re.I,
)
REPORT_ORCHESTRATION = re.compile(
    r"\b(report|spreadsheet|enrich|categorize|summarize|compile|build a list|deliverable)\b",
    re.I,
)
MULTI_ACTION = re.compile(
    r"\b(create|find|search|notify|post|send|update|add|log|draft)\b",
    re.I,
)
GOOGLE_WORKSPACE_FAMILY = frozenset({"google_drive", "google_sheets", "google_docs"})


@dataclass(frozen=True)
class OrchestrationStep:
    step_id: str
    segment: str
    label: str
    kind: str
    supported: bool
    requires_approval: bool
    plan: ConnectorActionPlan | None = None
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "step_id": self.step_id,
            "segment": self.segment,
            "label": self.label,
            "kind": self.kind,
            "supported": self.supported,
            "requires_approval": self.requires_approval,
            "skip_reason": self.skip_reason,
        }
        if self.plan:
            payload["plan"] = ChatConnectorExecutionService.plan_to_dict(self.plan)
        return payload

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> OrchestrationStep:
        plan_payload = payload.get("plan")
        plan = (
            ChatConnectorExecutionService.plan_from_dict(plan_payload)
            if isinstance(plan_payload, dict)
            else None
        )
        return OrchestrationStep(
            step_id=str(payload.get("step_id") or ""),
            segment=str(payload.get("segment") or ""),
            label=str(payload.get("label") or ""),
            kind=str(payload.get("kind") or "write"),
            supported=bool(payload.get("supported", True)),
            requires_approval=bool(payload.get("requires_approval")),
            plan=plan,
            skip_reason=payload.get("skip_reason"),
        )


class ChatOrchestrationService:
    """Plans and executes multi-connector chat workflows with governed step approvals."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._state = get_conversation_state_service(self.settings)
        self._connector = get_chat_connector_execution_service(self.settings)

    @staticmethod
    def is_orchestration_intent(
        message: str,
        task_state: dict[str, Any],
        connected_integrations: list[str],
        routing_tier: str | None = None,
    ) -> bool:
        pending = task_state.get("pending_task") or {}
        if str(pending.get("type") or "") == "connector_orchestration":
            return True
        text = message.strip()
        if len(text) < 12:
            return False
        integrations = ChatOrchestrationService._mentioned_integrations(text, connected_integrations)
        if len(integrations) >= 2:
            return True
        if len(integrations) >= 1 and MULTI_STEP_HINT.search(text):
            return True
        segments = ChatOrchestrationService._split_segments(text)
        if len(segments) >= 2 and len(integrations) >= 1:
            return True
        if connected_integrations and REPORT_ORCHESTRATION.search(text) and MULTI_STEP_HINT.search(text):
            return True
        if connected_integrations and len(segments) >= 2 and len(MULTI_ACTION.findall(text)) >= 2:
            return True
        if routing_tier in {"multi_step", "research"} and len(segments) >= 2 and connected_integrations:
            return True
        return False

    async def process_turn(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        message: str,
        classification: dict[str, Any],
        task_state: dict[str, Any],
        connected_integrations: list[str],
        client: Any,
        environment_name: str = "production",
    ) -> dict[str, Any] | None:
        if not self.is_orchestration_intent(message, task_state, connected_integrations):
            return None

        pending = task_state.get("pending_task") or {}
        pending_type = str(pending.get("type") or "")

        if DECLINE_PATTERN.match(message.strip()):
            await self._clear_orchestration(conversation_id, org_id)
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": "Cancelled — I won't run that orchestration. Tell me if you'd like a different approach.",
                "task_state": await self._state.get_task_state(conversation_id, org_id, client=client),
            }

        if pending_type != "connector_orchestration":
            steps = await self._build_plan(message, connected_integrations, org_id, user_id, classification)
            if len(steps) < 2:
                return None
            # STA-307 — zero runnable steps: terminal blocked state (no confirm / no wait loop).
            if not any(step.supported for step in steps):
                return await self._present_all_blocked_plan(
                    conversation_id,
                    org_id,
                    message,
                    steps,
                    client,
                )
            return await self._present_plan_confirm(
                conversation_id,
                org_id,
                user_id,
                message,
                steps,
                client,
            )

        status = str(pending.get("status") or "")
        confirmed = CONFIRM_PATTERN.match(message.strip()) or message.strip().lower() in {
            "confirm",
            "run",
            "execute",
            "approve",
        }

        if status == "awaiting_plan_confirm" and confirmed:
            return await self._start_execution(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                task_state=task_state,
                classification=classification,
                client=client,
                environment_name=environment_name,
            )

        if status == "awaiting_step_confirm" and confirmed:
            return await self._execute_current_step(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                task_state=task_state,
                classification=classification,
                client=client,
                environment_name=environment_name,
            )

        if status in {"awaiting_plan_confirm", "awaiting_step_confirm"}:
            refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
            return {
                "stop_pipeline": True,
                "dialogue_mode": "confirm",
                "message": self._reminder_message(task_state),
                "task_state": refreshed,
                "pending_task": self._pending_task_payload(task_state),
            }

        return None

    async def execute_confirmed_task(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        client: Any,
        classification: dict[str, Any] | None = None,
        environment_name: str = "production",
    ) -> ExecutionResult:
        task_state = await self._state.get_task_state(conversation_id, org_id, client=client)
        pending = task_state.get("pending_task") or {}
        if str(pending.get("type") or "") != "connector_orchestration":
            return ExecutionResult(
                success=False,
                entity_type="conversation",
                entity_id=conversation_id,
                result_url=f"/ai?conversation={conversation_id}",
                title="No orchestration",
                body="No pending multi-step orchestration to execute.",
            )
        status = str(pending.get("status") or "")
        if status == "awaiting_plan_confirm":
            turn = await self._start_execution(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                task_state=task_state,
                classification=classification or {},
                client=client,
                environment_name=environment_name,
            )
        elif status == "awaiting_step_confirm":
            turn = await self._execute_current_step(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                task_state=task_state,
                classification=classification or {},
                client=client,
                environment_name=environment_name,
            )
        else:
            return ExecutionResult(
                success=False,
                entity_type="conversation",
                entity_id=conversation_id,
                result_url=f"/ai?conversation={conversation_id}",
                title="Orchestration idle",
                body="Nothing is waiting for approval right now.",
            )
        execution = (turn or {}).get("execution_result") if turn else None
        if isinstance(execution, dict) and execution.get("success"):
            return ExecutionResult.from_dict(execution)
        if isinstance(execution, dict):
            return ExecutionResult.from_dict(execution)
        params = ((task_state or {}).get("clarified_params") or {}) if isinstance(task_state, dict) else {}
        run_id = str(params.get("orchestration_run_id") or "") or None
        return ExecutionResult(
            success=True,
            entity_type="orchestration",
            entity_id=run_id or conversation_id,
            result_url=resolve_orchestration_result_url(
                run_id=run_id,
                step_results=list(params.get("step_results") or []),
                conversation_id=conversation_id,
            ),
            title="Orchestration in progress",
            body=str((turn or {}).get("message") or "Continuing orchestration."),
            task_label="Multi-step orchestration",
        )

    async def _build_plan(
        self,
        message: str,
        connected_integrations: list[str],
        org_id: str,
        user_id: str,
        classification: dict[str, Any],
    ) -> list[OrchestrationStep]:
        segments = self._split_segments(message)
        if len(segments) < 2:
            segments = self._expand_single_segment(message, connected_integrations)
        steps: list[OrchestrationStep] = []
        for idx, segment in enumerate(segments, start=1):
            step = await self._plan_segment(
                step_id=f"step_{idx}",
                segment=segment,
                goal=message,
                connected_integrations=connected_integrations,
                org_id=org_id,
                user_id=user_id,
                classification=classification,
            )
            steps.append(step)
        return steps

    async def _plan_segment(
        self,
        *,
        step_id: str,
        segment: str,
        goal: str = "",
        connected_integrations: list[str],
        org_id: str,
        user_id: str,
        classification: dict[str, Any],
    ) -> OrchestrationStep:
        connected = {c.lower() for c in connected_integrations}
        # Prefer the vendor that appears first in *this* segment so multi-vendor
        # full-sentence leakage cannot label every step as the first org-wide hit.
        mentioned = self._mentioned_integrations_ordered(segment, connected_integrations)
        for integration in mentioned:
            if not self._integration_is_connected(integration, connected):
                return OrchestrationStep(
                    step_id=step_id,
                    segment=segment,
                    label=f"{integration.replace('_', ' ').title()} (not connected)",
                    kind="write",
                    supported=False,
                    requires_approval=False,
                    skip_reason=f"Connect {integration.replace('_', ' ').title()} in Gravitre to run this action.",
                )

        planning_text = self._segment_planning_text(segment, connected_integrations, goal=goal)
        plan = self._connector.plan_action(
            planning_text,
            connected_integrations=connected_integrations,
            task_state={},
        )
        if not plan:
            plan = self._connector.plan_fallback_segment(
                planning_text,
                connected_integrations=connected_integrations,
            )
        if not plan:
            reason = get_chat_action_mapper().skip_reason(
                segment,
                connected_integrations=connected_integrations,
            )
            return OrchestrationStep(
                step_id=step_id,
                segment=segment,
                label=f"Could not map: {segment[:80]}",
                kind="write",
                supported=False,
                requires_approval=False,
                skip_reason=reason or "No executable action matched this segment.",
            )

        risk = await self._connector._evaluate_risk(org_id, user_id, plan, classification)  # noqa: SLF001
        plan = ConnectorActionPlan(
            tool_name=plan.tool_name,
            invoke_action=plan.invoke_action,
            integration=plan.integration,
            kind=plan.kind,
            label=plan.label,
            args=dict(plan.args),
            destructive=plan.destructive,
            requires_approval=bool(risk.get("requires_approval") or plan.kind == "write"),
            approval_reason=risk.get("approval_reason"),
            inferred_fields=tuple(plan.inferred_fields or ()),
            inference_sources=dict(plan.inference_sources or {}),
        )
        # STA-305 — orchestration steps must carry the same omit-name inference
        # labeling as governed chat / ReAct (parallel-path parity).
        from app.services.chat_connector_execution_service import enrich_plan_inference_metadata

        plan = enrich_plan_inference_metadata(plan, message=goal or segment)
        return OrchestrationStep(
            step_id=step_id,
            segment=segment,
            label=plan.label,
            kind=plan.kind,
            supported=True,
            requires_approval=plan.requires_approval,
            plan=plan,
        )

    async def _present_all_blocked_plan(
        self,
        conversation_id: str,
        org_id: str,
        goal: str,
        steps: list[OrchestrationStep],
        client: Any,
    ) -> dict[str, Any]:
        """STA-307 — every step unsupported → immediate terminal blocked (no confirm)."""
        step_dicts = [step.to_dict() for step in steps]
        params = {
            "goal": goal,
            "steps": step_dicts,
            "current_step_index": len(steps),
            "step_results": [
                {
                    "step_id": step.step_id,
                    "label": step.label,
                    "success": False,
                    "summary": step.skip_reason or "Skipped unsupported step.",
                    "url": "/connectors",
                }
                for step in steps
            ],
            "total_steps": len(steps),
        }
        structured_plan = {
            "goal": goal,
            "steps": [
                {
                    "step_id": step.step_id,
                    "description": step.label,
                    "requires_approval": False,
                    "supported": False,
                }
                for step in steps
            ],
        }
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "current_plan": structured_plan,
                "pending_steps": [],
                "completed_steps": [],
                "clarified_params": params,
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "blocked",
                    "params": params,
                },
            },
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        lines = [self._format_step_line(idx, step) for idx, step in enumerate(steps, start=1)]
        reasons = [
            step.skip_reason or step.label
            for step in steps
            if step.skip_reason or step.label
        ]
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                f"I planned a **{len(steps)}-step orchestration**, but **nothing is runnable** "
                f"— every step is blocked:\n\n"
                + "\n".join(lines)
                + "\n\nConnect the required tools at /connectors (or rephrase with connectors "
                "you already have), then ask again. No approval is needed until at least one "
                "step can run."
                + (f"\n\nBlocked because: {'; '.join(reasons[:4])}" if reasons else "")
            ),
            "task_state": refreshed,
            "pending_task": self._pending_task_payload(refreshed),
            "execution_result": {
                "success": False,
                "entity_type": "orchestration",
                "entity_id": conversation_id,
                "result_url": "/connectors",
                "title": "Orchestration blocked — zero runnable steps",
                "body": "\n".join(lines),
                "task_label": "Multi-step orchestration blocked",
            },
        }

    async def _present_plan_confirm(
        self,
        conversation_id: str,
        org_id: str,
        user_id: str,
        goal: str,
        steps: list[OrchestrationStep],
        client: Any,
    ) -> dict[str, Any]:
        step_dicts = [step.to_dict() for step in steps]
        params = {
            "goal": goal,
            "steps": step_dicts,
            "current_step_index": 0,
            "step_results": [],
            "total_steps": len(steps),
        }
        structured_plan = {
            "goal": goal,
            "steps": [
                {
                    "step_id": step.step_id,
                    "description": step.label,
                    "requires_approval": step.requires_approval,
                    "supported": step.supported,
                }
                for step in steps
            ],
        }
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "current_plan": structured_plan,
                "pending_steps": [s for s in step_dicts if s.get("supported")],
                "completed_steps": [],
                "clarified_params": params,
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "awaiting_plan_confirm",
                    "params": params,
                },
            },
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        lines = [self._format_step_line(idx, step) for idx, step in enumerate(steps, start=1)]
        memory_hint = ""
        try:
            from app.services.execution_memory_service import get_execution_memory_service

            patterns = await get_execution_memory_service(self.settings).find_similar_patterns(
                org_id, goal, limit=1
            )
            memory_hint = get_execution_memory_service(self.settings).format_hint_for_plan(patterns)
        except Exception as exc:  # noqa: BLE001
            logger.debug("orchestration_execution_memory_skipped org_id=%s error=%s", org_id, exc)
        hint_block = f"\n\n_{memory_hint}_" if memory_hint else ""
        return {
            "stop_pipeline": True,
            "dialogue_mode": "confirm",
            "message": (
                f"I planned a **{len(steps)}-step orchestration**:\n\n"
                + "\n".join(lines)
                + "\n\nRead steps run automatically. Write steps require approval one at a time.\n\n"
                "Reply **yes** to approve the plan, or tell me what to change."
                + hint_block
            ),
            "task_state": refreshed,
            "pending_task": self._pending_task_payload(refreshed),
        }

    async def _start_execution(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        task_state: dict[str, Any],
        classification: dict[str, Any],
        client: Any,
        environment_name: str = "production",
    ) -> dict[str, Any]:
        params = dict((task_state.get("clarified_params") or {}))
        steps = [OrchestrationStep.from_dict(item) for item in params.get("steps") or []]
        if not steps:
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": "The orchestration plan is empty.",
                "task_state": task_state,
            }
        # STA-307 — confirm of an all-skipped plan must not enter a run/wait loop.
        if not any(step.supported and step.plan for step in steps):
            return await self._present_all_blocked_plan(
                conversation_id,
                org_id,
                str(params.get("goal") or "orchestration"),
                steps,
                client,
            )
        params["current_step_index"] = 0
        params["step_results"] = []
        run_id = start_orchestration_run(
            client,
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            goal=str(params.get("goal") or "Chat orchestration"),
            steps=[step.to_dict() for step in steps],
            environment_name=environment_name,
        )
        if run_id:
            params["orchestration_run_id"] = run_id
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "clarified_params": params,
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "running",
                    "params": params,
                },
            },
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        return await self._advance_orchestration(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            task_state=refreshed,
            classification=classification,
            client=client,
            environment_name=environment_name,
        )

    async def _execute_current_step(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        task_state: dict[str, Any],
        classification: dict[str, Any],
        client: Any,
        environment_name: str = "production",
    ) -> dict[str, Any]:
        params = dict((task_state.get("clarified_params") or {}))
        idx = int(params.get("current_step_index") or 0)
        steps = [OrchestrationStep.from_dict(item) for item in params.get("steps") or []]
        if idx >= len(steps):
            return await self._finalize_orchestration(
                conversation_id, org_id, user_id, params, client
            )

        step = steps[idx]
        if not step.supported or not step.plan:
            params["current_step_index"] = idx + 1
            await self._state.update_task_state(
                conversation_id,
                org_id,
                {"clarified_params": params, "pending_task": {"type": "connector_orchestration", "status": "running", "params": params}},
            )
            refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
            return await self._advance_orchestration(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                task_state=refreshed,
                classification=classification,
                client=client,
            )

        plan = self._enrich_plan_with_context(step.plan, params.get("step_results") or [])
        result = await self._connector.execute_plan(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            plan=plan,
            client=client,
            classification=classification,
            environment_name=environment_name,
        )
        step_results = list(params.get("step_results") or [])
        step_results.append(
            {
                "step_id": step.step_id,
                "label": step.label,
                "invoke_action": step.plan.invoke_action if step.plan else "",
                "success": result.success,
                "summary": result.body,
                "url": result.result_url,
                "structured": dict(result.structured or {}),
            }
        )
        completed = list(task_state.get("completed_steps") or [])
        completed.append(
            {
                "step_id": step.step_id,
                "label": step.label,
                "url": result.result_url,
                "entity_type": result.entity_type,
                "entity_id": result.entity_id,
            }
        )
        params["step_results"] = step_results
        params["current_step_index"] = idx + 1
        run_id = str(params.get("orchestration_run_id") or "") or None
        if run_id:
            sync_orchestration_step(
                client,
                org_id=org_id,
                run_id=run_id,
                step_id=step.step_id,
                success=bool(result.success),
                summary=result.body,
                result_url=result.result_url,
            )
        session_updates = self._orchestration_session_updates(
            task_state,
            step,
            result,
            completed_steps=completed,
            client=client,
            org_id=org_id,
            conversation_id=conversation_id,
        )
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "clarified_params": params,
                "completed_steps": completed,
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "running",
                    "params": params,
                },
                **session_updates,
            },
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        if not result.success:
            if run_id:
                finalize_orchestration_run(
                    client,
                    org_id=org_id,
                    run_id=run_id,
                    success=False,
                    summary=result.body,
                )
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": f"Step **{step.label}** failed: {result.body}",
                "execution_result": {
                    **serialize_execution_result(result),
                    "result_url": resolve_orchestration_result_url(
                        run_id=run_id,
                        step_results=step_results,
                        conversation_id=conversation_id,
                    ),
                },
                "task_state": refreshed,
            }
        return await self._advance_orchestration(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            task_state=refreshed,
            classification=classification,
            client=client,
            environment_name=environment_name,
        )

    async def _maybe_run_parallel_read_batch(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        steps: list[OrchestrationStep],
        params: dict[str, Any],
        idx: int,
        classification: dict[str, Any],
        client: Any,
        environment_name: str,
        run_id: str | None,
    ) -> dict[str, Any] | None:
        """Execute consecutive read-only steps in parallel (Tier 2)."""
        if idx >= len(steps):
            return None
        batch: list[tuple[int, OrchestrationStep]] = []
        cursor = idx
        while cursor < len(steps):
            step = steps[cursor]
            if (
                not step.supported
                or not step.plan
                or step.requires_approval
                or (step.kind or "read") != "read"
            ):
                break
            batch.append((cursor, step))
            cursor += 1
        if len(batch) < 2:
            return None

        async def _run_one(step: OrchestrationStep) -> ExecutionResult:
            plan = self._enrich_plan_with_context(step.plan, params.get("step_results") or [])
            return await self._connector.execute_plan(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                plan=plan,
                client=client,
                classification=classification,
                environment_name=environment_name,
            )

        results = await asyncio.gather(*[_run_one(step) for _, step in batch])
        step_results = list(params.get("step_results") or [])
        for (step_idx, step), result in zip(batch, results, strict=True):
            step_results.append(
                {
                    "step_id": step.step_id,
                    "label": step.label,
                    "invoke_action": step.plan.invoke_action if step.plan else "",
                    "success": result.success,
                    "summary": result.body,
                    "url": result.result_url,
                    "structured": dict(result.structured or {}),
                }
            )
            if run_id:
                sync_orchestration_step(
                    client,
                    org_id=org_id,
                    run_id=run_id,
                    step_id=step.step_id,
                    success=bool(result.success),
                    summary=result.body,
                    result_url=result.result_url,
                )
            if not result.success:
                if run_id:
                    finalize_orchestration_run(
                        client,
                        org_id=org_id,
                        run_id=run_id,
                        success=False,
                        summary=result.body,
                    )
                params["step_results"] = step_results
                params["current_step_index"] = step_idx + 1
                return {
                    "params": params,
                    "return_turn": {
                        "stop_pipeline": True,
                        "dialogue_mode": "answer",
                        "message": f"Step **{step.label}** failed: {result.body}",
                        "execution_result": serialize_execution_result(result),
                        "task_state": {"clarified_params": params},
                    },
                }

        params["step_results"] = step_results
        params["current_step_index"] = cursor
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "clarified_params": params,
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "running",
                    "params": params,
                },
            },
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        return {"params": params, "task_state": refreshed}

    async def _advance_orchestration(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        task_state: dict[str, Any],
        classification: dict[str, Any],
        client: Any,
        environment_name: str = "production",
    ) -> dict[str, Any]:
        params = dict((task_state.get("clarified_params") or {}))
        steps = [OrchestrationStep.from_dict(item) for item in params.get("steps") or []]
        idx = int(params.get("current_step_index") or 0)

        run_id = str(params.get("orchestration_run_id") or "") or None

        batch_result = await self._maybe_run_parallel_read_batch(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            steps=steps,
            params=params,
            idx=idx,
            classification=classification,
            client=client,
            environment_name=environment_name,
            run_id=run_id,
        )
        if batch_result is not None:
            params = batch_result["params"]
            idx = int(params.get("current_step_index") or 0)
            task_state = batch_result.get("task_state") or task_state
            if batch_result.get("return_turn"):
                return batch_result["return_turn"]

        while idx < len(steps):
            step = steps[idx]
            if not step.supported or not step.plan:
                skipped = list(params.get("step_results") or [])
                skipped.append(
                    {
                        "step_id": step.step_id,
                        "label": step.label,
                        "success": False,
                        "summary": step.skip_reason or "Skipped unsupported step.",
                        "url": "/connectors",
                    }
                )
                params["step_results"] = skipped
                params["current_step_index"] = idx + 1
                if run_id:
                    sync_orchestration_step(
                        client,
                        org_id=org_id,
                        run_id=run_id,
                        step_id=step.step_id,
                        success=False,
                        skipped=True,
                        summary=step.skip_reason or "Skipped — connector not connected.",
                        result_url="/connectors",
                    )
                idx += 1
                continue

            if step.requires_approval:
                params["current_step_index"] = idx
                await self._state.update_task_state(
                    conversation_id,
                    org_id,
                    {
                        "clarified_params": params,
                        "pending_task": {
                            "type": "connector_orchestration",
                            "status": "awaiting_step_confirm",
                            "params": params,
                            "current_step": step.to_dict(),
                        },
                    },
                )
                refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "confirm",
                    "message": (
                        f"**Step {idx + 1} of {len(steps)}** requires approval:\n\n"
                        f"**{step.label}** ({step.plan.invoke_action})\n\n"
                        f"{step.plan.approval_reason or 'This step changes data in a connected system.'}\n\n"
                        "Reply **yes** to run this step, or **no** to cancel."
                    ),
                    "task_state": refreshed,
                    "pending_task": self._pending_task_payload(refreshed),
                    "execution_result": {
                        "success": True,
                        "entity_type": "orchestration",
                        "entity_id": run_id or conversation_id,
                        "result_url": resolve_orchestration_result_url(
                            run_id=run_id,
                            step_results=list(params.get("step_results") or []),
                            conversation_id=conversation_id,
                        ),
                        "title": "Orchestration waiting on step approval",
                        "body": f"Approve step: {step.label}",
                        "task_label": "Multi-step orchestration",
                    },
                }

            plan = self._enrich_plan_with_context(step.plan, params.get("step_results") or [])
            result = await self._connector.execute_plan(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                plan=plan,
                client=client,
                classification=classification,
                environment_name=environment_name,
            )
            if not result.success:
                if run_id:
                    sync_orchestration_step(
                        client,
                        org_id=org_id,
                        run_id=run_id,
                        step_id=step.step_id,
                        success=False,
                        summary=result.body,
                        result_url=result.result_url,
                    )
                    finalize_orchestration_run(
                        client,
                        org_id=org_id,
                        run_id=run_id,
                        success=False,
                        summary=result.body,
                    )
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "answer",
                    "message": f"Step **{step.label}** failed: {result.body}",
                    "execution_result": {
                        **serialize_execution_result(result),
                        "result_url": resolve_orchestration_result_url(
                            run_id=run_id,
                            step_results=list(params.get("step_results") or []),
                            conversation_id=conversation_id,
                        ),
                    },
                    "task_state": task_state,
                }
            step_results = list(params.get("step_results") or [])
            step_results.append(
                {
                    "step_id": step.step_id,
                    "label": step.label,
                    "invoke_action": step.plan.invoke_action if step.plan else "",
                    "success": True,
                    "summary": result.body,
                    "url": result.result_url,
                    "structured": dict(result.structured or {}),
                }
            )
            params["step_results"] = step_results
            if run_id:
                sync_orchestration_step(
                    client,
                    org_id=org_id,
                    run_id=run_id,
                    step_id=step.step_id,
                    success=True,
                    summary=result.body,
                    result_url=result.result_url,
                )
            idx += 1
            params["current_step_index"] = idx

        return await self._finalize_orchestration(conversation_id, org_id, user_id, params, client)

    async def _finalize_orchestration(
        self,
        conversation_id: str,
        org_id: str,
        user_id: str,
        params: dict[str, Any],
        client: Any,
    ) -> dict[str, Any]:
        step_results = list(params.get("step_results") or [])
        successes = sum(1 for row in step_results if row.get("success"))
        lines = []
        for row in step_results:
            mark = "✓" if row.get("success") else "○"
            lines.append(f"- {mark} {row.get('label')}: {row.get('summary')}")
        summary_body = "\n".join(lines) if lines else "Orchestration finished."
        run_id = str(params.get("orchestration_run_id") or "") or None
        if run_id:
            finalize_orchestration_run(
                client,
                org_id=org_id,
                run_id=run_id,
                success=successes > 0,
                summary=summary_body,
            )
        primary_url = resolve_orchestration_result_url(
            run_id=run_id,
            step_results=step_results,
            conversation_id=conversation_id,
        )

        result = ExecutionResult(
            success=successes > 0,
            entity_type="workflow_run" if run_id else "orchestration",
            entity_id=run_id or conversation_id,
            result_url=primary_url,
            title=f"Orchestration complete ({successes}/{len(step_results)} steps)",
            body=summary_body,
            notification_type="task_completed",
            task_label="Multi-step orchestration complete",
        )
        emit_notification(
            client,
            org_id=org_id,
            user_id=user_id,
            event_type=result.notification_type,
            title=result.title,
            body=result.body[:500],
            entity_ref={
                "entity_type": result.entity_type,
                "entity_id": result.entity_id,
                "result_url": result.result_url,
            },
            channel_hints={"bell": True, "email": False},
        )
        try:
            from app.services.execution_memory_service import get_execution_memory_service

            await get_execution_memory_service(self.settings).record_orchestration_pattern(
                org_id=org_id,
                goal=str(params.get("goal") or "orchestration"),
                steps=list(params.get("steps") or []),
                success=successes > 0,
                run_id=run_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("orchestration_memory_record_skipped org_id=%s error=%s", org_id, exc)
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "clarified_params": params,
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "completed",
                    "result": serialize_execution_result(result),
                },
                "pending_steps": [],
            },
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                f"**Orchestration complete** ({successes}/{len(step_results)} steps succeeded).\n\n"
                f"{summary_body}"
                + (f"\n\n[View run details]({primary_url})" if primary_url else "")
            ),
            "execution_result": serialize_execution_result(result),
            "task_state": refreshed,
        }

    async def _clear_orchestration(self, conversation_id: str, org_id: str) -> None:
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "pending_task": None,
                "clarified_params": {},
                "current_plan": None,
                "pending_steps": [],
            },
        )

    @staticmethod
    def _pending_task_payload(task_state: dict[str, Any]) -> dict[str, Any]:
        pending = dict(task_state.get("pending_task") or {})
        params = dict((task_state.get("clarified_params") or pending.get("params") or {}))
        payload = {
            "type": "connector_orchestration",
            "params": params,
        }
        if pending.get("status"):
            payload["status"] = pending.get("status")
        if pending.get("current_step"):
            payload["current_step"] = pending.get("current_step")
        return payload

    @staticmethod
    def _reminder_message(task_state: dict[str, Any]) -> str:
        pending = task_state.get("pending_task") or {}
        status = str(pending.get("status") or "")
        params = dict((task_state.get("clarified_params") or {}))
        if status == "awaiting_plan_confirm":
            return "Reply **yes** to approve the orchestration plan, or tell me what to adjust."
        idx = int(params.get("current_step_index") or 0) + 1
        total = int(params.get("total_steps") or len(params.get("steps") or []))
        current = pending.get("current_step") or {}
        label = current.get("label") or f"step {idx}"
        return f"Reply **yes** to approve **{label}** (step {idx} of {total}), or **no** to cancel."

    @staticmethod
    def _format_step_line(index: int, step: OrchestrationStep) -> str:
        if not step.supported:
            return f"{index}. ○ {step.label} — *skipped* ({step.skip_reason})"
        approval = "approval required" if step.requires_approval else "auto-run"
        kind = step.kind or "action"
        return f"{index}. **{step.label}** ({kind}, {approval})"

    @staticmethod
    def _integration_is_connected(integration: str, connected: set[str]) -> bool:
        key = integration.lower()
        if key in connected:
            return True
        if key in GOOGLE_WORKSPACE_FAMILY and connected & GOOGLE_WORKSPACE_FAMILY:
            return True
        return False

    @staticmethod
    def _segment_planning_text(
        segment: str,
        connected_integrations: list[str],
        *,
        goal: str = "",
    ) -> str:
        text = segment.strip()
        if ChatOrchestrationService._mentioned_integrations(text, connected_integrations):
            return text
        connected = [c.lower() for c in connected_integrations]
        if len(connected) == 1:
            alias = INTEGRATION_ALIASES.get(connected[0], (connected[0],))[0]
            return f"{text} in {alias}"
        goal_vendors = ChatOrchestrationService._mentioned_integrations(goal, connected_integrations)
        if len(goal_vendors) == 1:
            alias = INTEGRATION_ALIASES.get(goal_vendors[0], (goal_vendors[0],))[0]
            return f"{text} in {alias}"
        return text

    @staticmethod
    def _split_segments(message: str) -> list[str]:
        text = message.strip()
        parts = [text]
        for pattern in (SEGMENT_COMMA, MULTI_STEP_SPLIT):
            next_parts: list[str] = []
            for part in parts:
                next_parts.extend(p.strip(" .") for p in pattern.split(part) if p and p.strip(" ."))
            parts = next_parts
        return parts

    @staticmethod
    def _expand_single_segment(message: str, connected_integrations: list[str]) -> list[str]:
        """Split a single sentence that mentions multiple integrations.

        STA-307: previous `[^,.;]*vendor[^,.;]*` matcher returned the *entire*
        sentence for every vendor (\"and\" is allowed), so both steps inherited
        HubSpot-first labeling. Prefer conjunction splits, then local clauses.
        """
        text = message.strip()
        integrations = ChatOrchestrationService._mentioned_integrations(text, connected_integrations)
        if len(integrations) < 2:
            return [text]

        pieces = [
            p.strip(" .")
            for p in re.split(r"\s+and\s+|\s*;\s*|\s+then\s+|\s+and then\s+", text, flags=re.I)
            if p and p.strip(" .")
        ]
        if len(pieces) >= 2:
            mapped: list[str] = []
            for piece in pieces:
                if ChatOrchestrationService._mentioned_integrations(piece, connected_integrations):
                    mapped.append(piece)
            # Keep only if we still cover ≥2 distinct vendors across pieces.
            vendors_seen: list[str] = []
            for piece in mapped:
                for v in ChatOrchestrationService._mentioned_integrations(piece, connected_integrations):
                    if v not in vendors_seen:
                        vendors_seen.append(v)
            if len(mapped) >= 2 and len(vendors_seen) >= 2:
                return mapped

        segments: list[str] = []
        lowered = text.lower()
        for integration in integrations:
            aliases = INTEGRATION_ALIASES.get(integration, (integration,))
            alias = next(
                (
                    a
                    for a in aliases
                    if re.search(rf"\b{re.escape(a)}\b", lowered)
                ),
                integration,
            )
            # Clause ending at next conjunction / punctuation after the alias.
            pattern = re.compile(
                rf"((?:^|[,;]|\band\b|\bthen\b)\s*)?([^.|;]*?\b{re.escape(alias)}\b[^.|;]*?)(?=\s+\band\b|\s+\bthen\b|[.;]|$)",
                re.I,
            )
            match = pattern.search(text)
            if match:
                clause = (match.group(2) or "").strip(" ,.")
                if clause and clause not in segments:
                    segments.append(clause)
        return segments if len(segments) >= 2 else [text]

    @staticmethod
    def _alias_matches(alias: str, lowered: str) -> bool:
        """Word-boundary match so short aliases (gh, crm) don't hit substrings."""
        a = (alias or "").strip().lower()
        if not a:
            return False
        if " " in a:
            return a in lowered
        return bool(re.search(rf"\b{re.escape(a)}\b", lowered))

    @staticmethod
    def _mentioned_integrations(message: str, connected_integrations: list[str]) -> list[str]:
        lowered = message.lower()
        found: list[str] = []
        for integration, aliases in INTEGRATION_ALIASES.items():
            if any(ChatOrchestrationService._alias_matches(alias, lowered) for alias in aliases):
                if integration not in found:
                    found.append(integration)
        return found

    @staticmethod
    def _mentioned_integrations_ordered(message: str, connected_integrations: list[str]) -> list[str]:
        """Same as _mentioned_integrations but ordered by first appearance in text."""
        lowered = message.lower()
        found = ChatOrchestrationService._mentioned_integrations(message, connected_integrations)

        def first_pos(integration: str) -> int:
            aliases = INTEGRATION_ALIASES.get(integration, (integration,))
            positions = []
            for alias in aliases:
                if " " in alias:
                    idx = lowered.find(alias)
                else:
                    m = re.search(rf"\b{re.escape(alias)}\b", lowered)
                    idx = m.start() if m else -1
                if idx >= 0:
                    positions.append(idx)
            return min(positions) if positions else 10**9

        return sorted(found, key=first_pos)
    @staticmethod
    def _enrich_plan_with_context(
        plan: ConnectorActionPlan,
        prior_results: list[dict[str, Any]],
    ) -> ConnectorActionPlan:
        session = load_connector_session({})
        for row in prior_results:
            if not isinstance(row, dict):
                continue
            step_id = str(row.get("step_id") or row.get("stepId") or "").strip()
            if not step_id:
                continue
            session = record_step_output(
                session,
                step_id=step_id,
                invoke_action=str(row.get("invoke_action") or row.get("invokeAction") or plan.invoke_action),
                label=str(row.get("label") or step_id),
                success=bool(row.get("success")),
                summary=str(row.get("summary") or ""),
                url=row.get("url"),
                structured=dict(row.get("structured") or {}),
            )
        enriched = bind_plan_from_session(plan, session)
        if enriched.integration != "slack" or enriched.invoke_action != "slack.post_message":
            return enriched
        summaries = [str(row.get("summary") or "") for row in prior_results if row.get("summary")]
        if not summaries:
            return enriched
        args = dict(enriched.args)
        prefix = "Orchestration summary:\n" + "\n".join(f"- {line}" for line in summaries[-3:])
        existing = str(args.get("message") or "").strip()
        args["message"] = f"{existing}\n\n{prefix}".strip() if existing else prefix
        return ConnectorActionPlan(
            tool_name=enriched.tool_name,
            invoke_action=enriched.invoke_action,
            integration=enriched.integration,
            kind=enriched.kind,
            label=enriched.label,
            args=args,
            requires_approval=enriched.requires_approval,
            approval_reason=enriched.approval_reason,
            destructive=enriched.destructive,
            inferred_fields=enriched.inferred_fields,
            inference_sources=enriched.inference_sources,
        )

    @staticmethod
    def _orchestration_session_updates(
        task_state: dict[str, Any],
        step: OrchestrationStep,
        result: ExecutionResult,
        *,
        completed_steps: list[dict[str, Any]],
        client: Any | None = None,
        org_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        session = load_connector_session(task_state)
        invoke_action = step.plan.invoke_action if step.plan else ""
        session = record_step_output(
            session,
            step_id=step.step_id,
            invoke_action=invoke_action,
            label=step.label,
            success=result.success,
            summary=result.body,
            url=result.result_url,
            structured=dict(result.structured or {}),
        )
        if result.success and step.plan:
            session = record_entity_from_execution(
                session,
                integration=step.plan.integration,
                invoke_action=step.plan.invoke_action,
                entity_id=result.entity_id or None,
                structured=dict(result.structured or {}),
                label=step.label,
                client=client,
                org_id=org_id,
                conversation_id=conversation_id,
            )
        session = replace(
            session,
            session_summary=build_session_summary(
                completed_steps=completed_steps,
                step_outputs=session.step_outputs,
                active_entities=session.active_entities,
            ),
        )
        return {
            **connector_session_patch(session),
            "resolved_entities": sync_legacy_resolved_entities(session),
        }


_chat_orchestration_service: ChatOrchestrationService | None = None


def get_chat_orchestration_service(settings: Settings | None = None) -> ChatOrchestrationService:
    global _chat_orchestration_service
    if _chat_orchestration_service is None or settings is not None:
        _chat_orchestration_service = ChatOrchestrationService(settings)
    return _chat_orchestration_service
