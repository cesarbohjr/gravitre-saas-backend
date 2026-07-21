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
from app.services.gravitree_voice import format_operator_message
from app.services.conversational_execution_service import (
    CONFIRM_PATTERN,
    DECLINE_PATTERN,
    ExecutionResult,
)
from app.services.chat_orchestration_runs import (
    finalize_orchestration_run,
    first_external_step_url,
    orchestration_run_fully_completed,
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


def _vendor_url_from_execution(result: ExecutionResult) -> str | None:
    """Prefer explicit external_url; fall back to http result_url for legacy steps."""
    external = str(getattr(result, "external_url", None) or "").strip()
    if external.startswith(("http://", "https://")):
        return external
    url = str(result.result_url or "").strip()
    if url.startswith(("http://", "https://")):
        return url
    structured = result.structured if isinstance(result.structured, dict) else {}
    nested = str(structured.get("external_url") or "").strip()
    if nested.startswith(("http://", "https://")):
        return nested
    return None


def _step_result_row(step: Any, result: ExecutionResult) -> dict[str, Any]:
    vendor_url = _vendor_url_from_execution(result)
    return {
        "step_id": step.step_id,
        "label": step.label,
        "invoke_action": step.plan.invoke_action if getattr(step, "plan", None) else "",
        "success": result.success,
        "summary": result.body,
        "url": vendor_url,
        "external_url": vendor_url,
        "primary_url": result.result_url,
        "structured": dict(result.structured or {}),
    }


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
# Wave 6–7 / STA-325 — meta "outline a plan before tools" is not an orchestration step.
META_PLAN_SEGMENT = re.compile(
    r"\b(?:outline|draft|share|show|give\s+me|write)\s+(?:a\s+|an\s+|the\s+|my\s+)?"
    r"(?:short\s+|brief\s+|quick\s+)?plan\b|"
    r"\bplan\s+before\s+(?:calling\s+)?tools\b|"
    r"\bbefore\s+(?:calling\s+)?tools\b",
    re.I,
)
PLAN_TWEAK = re.compile(
    r"\b(change|adjust|modify|instead|skip|swap|remove\s+step|add\s+step|"
    r"wait|hold\s+on|different\s+plan|revise)\b",
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
            # Only live approval gates keep the orch pipeline; completed/failed
            # must not hijack unrelated turns or coincidental "yes" confirms.
            status = str(pending.get("status") or "")
            if status in {"awaiting_plan_confirm", "awaiting_step_confirm"}:
                return True
        text = message.strip()
        if len(text) < 12:
            return False
        integrations = ChatOrchestrationService._mentioned_integrations(text, connected_integrations)
        if len(integrations) >= 2:
            return True
        segments = ChatOrchestrationService._split_segments(text)
        actionable = [
            segment
            for segment in segments
            if not ChatOrchestrationService._is_meta_plan_segment(segment)
        ]
        # STA-325 — "do X, then outline a plan before tools" is a single ReAct turn,
        # not multi-step connector orchestration awaiting_plan_confirm.
        if len(integrations) >= 1 and MULTI_STEP_HINT.search(text):
            if len(actionable) >= 2 or len(integrations) >= 2:
                return True
        if len(actionable) >= 2 and len(integrations) >= 1:
            return True
        if (
            connected_integrations
            and REPORT_ORCHESTRATION.search(text)
            and MULTI_STEP_HINT.search(text)
            and len(actionable) >= 2
        ):
            return True
        if connected_integrations and len(actionable) >= 2 and len(MULTI_ACTION.findall(text)) >= 2:
            return True
        if (
            routing_tier in {"multi_step", "research"}
            and len(actionable) >= 2
            and connected_integrations
        ):
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
        # Reload — caller may hold a stale snapshot after ledger/pre-stream writes.
        try:
            task_state = await self._state.get_task_state(
                conversation_id, org_id, client=client
            )
        except Exception:  # noqa: BLE001
            pass

        pending = task_state.get("pending_task") or {}
        pending_type = str(pending.get("type") or "")
        pending_status = str(pending.get("status") or "")

        # Module B — resolved plans must close out; do not leave sticky state for
        # a later bare "yes" or unrelated question to revive.
        if pending_type == "connector_orchestration" and pending_status in {
            "completed",
            "failed",
            "cancelled",
        }:
            await self._clear_orchestration(conversation_id, org_id)
            task_state = await self._state.get_task_state(
                conversation_id, org_id, client=client
            )
            pending = task_state.get("pending_task") or {}
            pending_type = str(pending.get("type") or "")
            pending_status = str(pending.get("status") or "")

        if (
            pending_type == "connector_orchestration"
            and pending_status in {"awaiting_plan_confirm", "awaiting_step_confirm"}
            and self._should_supersede_pending_orchestration(
                message,
                task_state,
                connected_integrations,
            )
        ):
            await self._clear_orchestration(conversation_id, org_id)
            return None

        if not self.is_orchestration_intent(message, task_state, connected_integrations):
            return None

        from app.services.pending_reply_classifier import (
            build_pending_snapshot,
            classify_pending_reply,
            emit_pending_reply_audit,
            format_ambiguous_clarify,
            format_pending_meta_answer,
            format_unrelated_hold_prompt,
            has_pending_family,
        )

        status = str(pending.get("status") or "")
        # Shared 7-way classifier for active orch pending — before reminder traps.
        if pending_type == "connector_orchestration" and status in {
            "awaiting_plan_confirm",
            "awaiting_step_confirm",
        }:
            snap = build_pending_snapshot(task_state)
            intent = await classify_pending_reply(
                message,
                task_state=task_state,
                settings=self.settings,
                org_id=org_id,
                use_model=True,
            )
            emit_pending_reply_audit(
                client=client,
                org_id=org_id,
                actor_id=user_id,
                conversation_id=conversation_id,
                intent=intent,
                snap=snap,
            )
            try:
                await self._state.update_task_state(
                    conversation_id,
                    org_id,
                    {"last_pending_reply_intent": intent},
                    client=client,
                )
            except Exception:  # noqa: BLE001
                pass

            if intent == "reject":
                await self._clear_orchestration(conversation_id, org_id)
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "answer",
                    "message": (
                        "Cancelled — I won't run that orchestration. "
                        "Tell me if you'd like a different approach."
                    ),
                    "task_state": await self._state.get_task_state(
                        conversation_id, org_id, client=client
                    ),
                    "pending_reply_intent": intent,
                }

            if intent == "meta_clarify":
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "clarifying",
                    "message": format_pending_meta_answer(snap),
                    "task_state": task_state,
                    "pending_task": self._pending_task_payload(task_state),
                    "pending_reply_intent": intent,
                }

            if intent == "unrelated":
                patch = {
                    "pending_hold_prompt": True,
                    "pending_hold_new_request": message,
                    "last_pending_reply_intent": intent,
                }
                await self._state.update_task_state(
                    conversation_id, org_id, patch, client=client
                )
                refreshed = await self._state.get_task_state(
                    conversation_id, org_id, client=client
                )
                hold = format_unrelated_hold_prompt(snap, new_request=message)
                message_out = hold
                try:
                    from app.services.conversational_reply_service import (
                        compose_pending_social_aside,
                    )

                    composed = await compose_pending_social_aside(
                        message,
                        task_state=refreshed,
                        sober_fallback=hold,
                        settings=self.settings,
                        org_id=org_id,
                    )
                    if composed:
                        message_out = composed
                except Exception:  # noqa: BLE001
                    message_out = hold
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "clarifying",
                    "message": message_out,
                    "task_state": refreshed,
                    "pending_task": self._pending_task_payload(refreshed),
                    "pending_reply_intent": intent,
                }

            if intent == "ambiguous":
                clarify = format_ambiguous_clarify(snap)
                message_out = clarify
                try:
                    from app.services.conversational_reply_service import (
                        compose_pending_social_aside,
                    )

                    composed = await compose_pending_social_aside(
                        message,
                        task_state=task_state,
                        sober_fallback=clarify,
                        settings=self.settings,
                        org_id=org_id,
                    )
                    if composed:
                        message_out = composed
                except Exception:  # noqa: BLE001
                    message_out = clarify
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "clarifying",
                    "message": message_out,
                    "task_state": task_state,
                    "pending_task": self._pending_task_payload(task_state),
                    "pending_reply_intent": intent,
                    "block_fabrication": True,
                }

            if intent == "modify":
                await self._clear_orchestration(conversation_id, org_id)
                # Fall through to build a new plan from the modify instruction.
                pending_type = ""
                pending = {}
                status = ""
                task_state = await self._state.get_task_state(
                    conversation_id, org_id, client=client
                )

            if intent == "confirm":
                if status == "awaiting_plan_confirm":
                    return await self._start_execution(
                        org_id=org_id,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        task_state=task_state,
                        classification=classification,
                        client=client,
                        environment_name=environment_name,
                    )
                if status == "awaiting_step_confirm":
                    return await self._execute_current_step(
                        org_id=org_id,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        task_state=task_state,
                        classification=classification,
                        client=client,
                        environment_name=environment_name,
                    )

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
            "yes",
            "y",
            "yeah",
            "yep",
            "ok",
            "okay",
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
            # Fallback: prefer hold/abandon prompt over silent supersede or yes-reminder.
            snap = build_pending_snapshot(task_state)
            if has_pending_family(task_state):
                patch = {
                    "pending_hold_prompt": True,
                    "pending_hold_new_request": message,
                    "last_pending_reply_intent": "unrelated",
                }
                await self._state.update_task_state(
                    conversation_id, org_id, patch, client=client
                )
                refreshed = await self._state.get_task_state(
                    conversation_id, org_id, client=client
                )
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "clarifying",
                    "message": format_unrelated_hold_prompt(snap, new_request=message),
                    "task_state": refreshed,
                    "pending_task": self._pending_task_payload(refreshed),
                    "pending_reply_intent": "unrelated",
                }
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
                    skip_reason=format_operator_message(
                        "connector_connect_to_run",
                        integration=integration,
                        confidence_register="blocked",
                        allow_humor=False,
                    ),
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
                skip_reason=reason
                or format_operator_message(
                    "no_executable_action",
                    confidence_register="blocked",
                    allow_humor=False,
                ),
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
                    "summary": step.skip_reason
                    or format_operator_message(
                        "skipped_unsupported",
                        confidence_register="blocked",
                        allow_humor=False,
                    ),
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
            client=client,
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
        step_results.append(_step_result_row(step, result))
        completed = list(task_state.get("completed_steps") or [])
        completed.append(
            {
                "step_id": step.step_id,
                "label": step.label,
                "url": result.result_url,
                "external_url": _vendor_url_from_execution(result),
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
                result_url=_vendor_url_from_execution(result),
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
                    user_id=user_id,
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

        # Phase 2 A/B — honor X-Gravitree-React-Serial / GRAVITREE_REACT_SERIAL_TOOLS
        # so orchestration multi-read batches share the same baseline as ReAct.
        from app.operators.react_engine import _serial_tools_forced

        import time as _time

        started = _time.perf_counter()
        if _serial_tools_forced():
            results = []
            for _, step in batch:
                results.append(await _run_one(step))
            parallel = False
        else:
            results = list(await asyncio.gather(*[_run_one(step) for _, step in batch]))
            parallel = True
        batch_elapsed_ms = int((_time.perf_counter() - started) * 1000)
        params["orchestration_perf"] = {
            "parallelBatch": parallel,
            "batchSize": len(batch),
            "batchElapsedMs": batch_elapsed_ms,
            "steps": [step.label for _, step in batch],
        }
        step_results = list(params.get("step_results") or [])
        for (step_idx, step), result in zip(batch, results, strict=True):
            step_results.append(_step_result_row(step, result))
            if run_id:
                sync_orchestration_step(
                    client,
                    org_id=org_id,
                    run_id=run_id,
                    step_id=step.step_id,
                    success=bool(result.success),
                    summary=result.body,
                    result_url=_vendor_url_from_execution(result),
                )
            if not result.success:
                if run_id:
                    finalize_orchestration_run(
                        client,
                        org_id=org_id,
                        run_id=run_id,
                        success=False,
                        summary=result.body,
                        user_id=user_id,
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
                        "skipped": True,
                        "summary": step.skip_reason
                        or format_operator_message(
                            "skipped_unsupported",
                            confidence_register="blocked",
                            allow_humor=False,
                        ),
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
                        summary=step.skip_reason
                        or format_operator_message(
                            "skipped_unsupported",
                            confidence_register="blocked",
                            allow_humor=False,
                        ),
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
                        result_url=_vendor_url_from_execution(result),
                    )
                    finalize_orchestration_run(
                        client,
                        org_id=org_id,
                        run_id=run_id,
                        success=False,
                        summary=result.body,
                        user_id=user_id,
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
            step_results.append(_step_result_row(step, result))
            params["step_results"] = step_results
            if run_id:
                sync_orchestration_step(
                    client,
                    org_id=org_id,
                    run_id=run_id,
                    step_id=step.step_id,
                    success=True,
                    summary=result.body,
                    result_url=_vendor_url_from_execution(result),
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
        run_ok = orchestration_run_fully_completed(step_results)
        lines = []
        for row in step_results:
            mark = "✓" if row.get("success") else "○"
            lines.append(f"- {mark} {row.get('label')}: {row.get('summary')}")
        summary_body = "\n".join(lines) if lines else "Orchestration finished."
        run_id = str(params.get("orchestration_run_id") or "") or None
        # Prefer a late run when steps exist so Module A fanout has a Runs row.
        if not run_id:
            steps_for_run = list(params.get("steps") or [])
            if steps_for_run:
                late_run_id = start_orchestration_run(
                    client,
                    org_id=org_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    goal=str(params.get("goal") or "Chat orchestration"),
                    steps=steps_for_run,
                )
                if late_run_id:
                    run_id = late_run_id
                    params["orchestration_run_id"] = run_id
        if run_id:
            finalize_orchestration_run(
                client,
                org_id=org_id,
                run_id=run_id,
                success=run_ok,
                summary=summary_body,
                user_id=user_id,
            )
        else:
            # Orphan path: no run_id and no steps to create one — still fan out.
            from app.services.execution_outcome import VerifiedOutputRef, finalize_execution_outcome

            finalize_execution_outcome(
                client,
                org_id=org_id,
                status="completed" if run_ok else "failed",
                source="chat_orch",
                actor_id=user_id,
                persist_run=False,
                error_summary=None if run_ok else summary_body,
                verified_output=VerifiedOutputRef(
                    summary=summary_body[:2000] or None,
                    result_url=f"/ai?conversation={conversation_id}",
                    entity_type="conversation",
                    entity_id=conversation_id,
                ),
                notification_title=(
                    f"Orchestration complete ({successes}/{len(step_results)} steps)"
                    if run_ok
                    else f"Orchestration failed ({successes}/{len(step_results)} steps succeeded)"
                ),
                notification_body=summary_body[:500],
                metadata={
                    "path": "chat_orchestration_orphan",
                    "conversation_id": conversation_id,
                },
            )
        primary_url = resolve_orchestration_result_url(
            run_id=run_id,
            step_results=step_results,
            conversation_id=conversation_id,
        )
        external_url = first_external_step_url(step_results)
        goal = str(params.get("goal") or "Chat orchestration")
        result = ExecutionResult(
            success=run_ok,
            entity_type="workflow_run" if run_id else "orchestration",
            entity_id=run_id or conversation_id,
            result_url=primary_url,
            external_url=external_url,
            title=(
                f"Orchestration complete ({successes}/{len(step_results)} steps)"
                if run_ok
                else f"Orchestration failed ({successes}/{len(step_results)} steps succeeded)"
            ),
            body=summary_body,
            notification_type="task_completed" if run_ok else "run_failed",
            task_label=(
                "Multi-step orchestration complete"
                if run_ok
                else "Multi-step orchestration failed"
            ),
            structured={
                "runId": run_id,
                "conversationId": conversation_id,
                "goal": goal,
                "external_url": external_url,
                "step_results": step_results,
                "source": "chat_orchestration",
            },
        )
        try:
            from app.services.execution_memory_service import get_execution_memory_service

            await get_execution_memory_service(self.settings).record_orchestration_pattern(
                org_id=org_id,
                goal=str(params.get("goal") or "orchestration"),
                steps=list(params.get("steps") or []),
                success=run_ok,
                run_id=run_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("orchestration_memory_record_skipped org_id=%s error=%s", org_id, exc)
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "clarified_params": {},
                "current_plan": None,
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "completed" if run_ok else "failed",
                    "result": serialize_execution_result(result),
                },
                "pending_steps": [],
                "completed_steps": [],
            },
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        from app.services.post_action_experience_service import enrich_execution_turn

        turn = enrich_execution_turn(
            message="",
            execution=result,
            plan=None,
            task_state=refreshed,
            step_results=step_results,
        )
        # Always keep orchestration headline + per-step body (enrich formats single-action copy).
        means = (turn.get("post_action_experience") or {}).get("whatThisMeans") or ""
        headline = (
            f"**Orchestration complete** ({successes}/{len(step_results)} steps succeeded)."
            if run_ok
            else f"**Orchestration failed** ({successes}/{len(step_results)} steps succeeded)."
        )
        turn["message"] = (
            f"{headline}\n\n{summary_body}"
            + (f"\n\n_What this means:_ {means}" if means else "")
            + (f"\n\n[View run details]({primary_url})" if primary_url else "")
        )
        if run_ok:
            rec = (turn.get("execution_result") or {}).get("recommendation") or (
                (turn.get("post_action_experience") or {}).get("recommendation")
            )
            if isinstance(rec, dict) and rec.get("suggestedUtterance"):
                turn["message"] += (
                    f"\n\n**What I'd look at next:** {rec.get('title')} — {rec.get('reason')}\n"
                    f"_Suggest only — reply_ **{rec['suggestedUtterance']}** "
                    f"_to proceed (nothing runs until you approve)._"
                )
        else:
            bridge = (turn.get("execution_result") or {}).get("failure_bridge") or (
                (turn.get("post_action_experience") or {}).get("failureBridge")
            )
            if isinstance(bridge, dict) and bridge.get("prompt"):
                turn["message"] += f"\n\n{bridge['prompt']}"
        turn["orchestration_perf"] = params.get("orchestration_perf")
        return turn

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
    def _is_meta_plan_segment(segment: str) -> bool:
        """True when the clause is only 'show a plan / plan before tools' meta-instruction."""
        text = (segment or "").strip()
        if not text:
            return True
        if not META_PLAN_SEGMENT.search(text):
            return False
        # Keep real work that happens to mention planning ("plan a Slack post…").
        if MULTI_ACTION.search(text) and not re.search(
            r"\bplan\s+before\s+(?:calling\s+)?tools\b", text, re.I
        ):
            # "outline a plan to create X" still has create — treat as actionable.
            if re.search(
                r"\b(?:create|find|search|notify|post|send|update|add|log)\b",
                text,
                re.I,
            ):
                return False
        return True

    @staticmethod
    def _should_supersede_pending_orchestration(
        message: str,
        task_state: dict[str, Any],
        connected_integrations: list[str],
    ) -> bool:
        """Drop stale awaiting_* orch when the user starts a clearly new task."""
        text = (message or "").strip()
        if len(text) < 12:
            return False
        if PLAN_TWEAK.search(text) and len(text) < 160:
            return False
        # Informational / run-history asks are never orch confirms.
        try:
            from app.services.factual_claim_honesty import is_run_history_question

            if is_run_history_question(text):
                return True
        except Exception:  # noqa: BLE001
            pass
        if re.search(
            r"\b(what|which|how\s+many|show\s+me|list|status|have\s+been)\b",
            text,
            re.I,
        ) and not re.search(
            r"\b(plan|step|orchestration|approve|confirm|yes|yep|ok)\b",
            text,
            re.I,
        ):
            return True
        params = dict(
            (task_state.get("clarified_params") or {})
            or ((task_state.get("pending_task") or {}).get("params") or {})
        )
        goal = str(params.get("goal") or "")
        pending_integrations = set(
            ChatOrchestrationService._mentioned_integrations(goal, connected_integrations)
        )
        message_integrations = set(
            ChatOrchestrationService._mentioned_integrations(text, connected_integrations)
        )
        if (
            message_integrations
            and pending_integrations
            and message_integrations.isdisjoint(pending_integrations)
        ):
            return True
        # Same vendor family but a fresh imperative that doesn't reference the plan.
        if MULTI_ACTION.search(text) and not re.search(
            r"\b(plan|step|orchestration|approve|confirm)\b", text, re.I
        ):
            goal_l = goal.lower()
            text_l = text.lower()
            if goal_l and text_l[:48] not in goal_l and goal_l[:48] not in text_l:
                return True
        return False

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
