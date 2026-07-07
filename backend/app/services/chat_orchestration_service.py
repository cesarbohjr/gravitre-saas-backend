"""Multi-connector chat orchestration with plan confirm and step-by-step approval."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
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
from app.services.notification_service import create_user_notification

logger = get_logger(__name__)

MULTI_STEP_SPLIT = re.compile(
    r"(?:,\s+and\s+|\s+;\s+|\s+then\s+|\s+and then\s+|\s+and\s+(?=notify|create|post|send|update|add|log)\b)",
    re.I,
)
SEGMENT_COMMA = re.compile(
    r",\s*(?=(?:create|build|make|post|send|notify|update|add|log)\b)",
    re.I,
)
MULTI_STEP_HINT = re.compile(
    r"\b(then|and then|after that|followed by|next,|also notify|and notify)\b",
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
        return len(segments) >= 2 and len(integrations) >= 1

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
                url="/ai",
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
                url="/ai",
                title="Orchestration idle",
                body="Nothing is waiting for approval right now.",
            )
        execution = (turn or {}).get("execution_result") if turn else None
        if isinstance(execution, dict) and execution.get("success"):
            return ExecutionResult(**execution)
        if isinstance(execution, dict):
            return ExecutionResult(**execution)
        return ExecutionResult(
            success=True,
            entity_type="orchestration",
            entity_id=conversation_id,
            url="/ai",
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
        mentioned = self._mentioned_integrations(segment, connected_integrations)
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
        )
        return OrchestrationStep(
            step_id=step_id,
            segment=segment,
            label=plan.label,
            kind=plan.kind,
            supported=True,
            requires_approval=plan.requires_approval,
            plan=plan,
        )

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
        return {
            "stop_pipeline": True,
            "dialogue_mode": "confirm",
            "message": (
                f"I planned a **{len(steps)}-step orchestration**:\n\n"
                + "\n".join(lines)
                + "\n\nRead steps run automatically. Write steps require approval one at a time.\n\n"
                "Reply **yes** to approve the plan, or tell me what to change."
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
        params["current_step_index"] = 0
        params["step_results"] = []
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
                "success": result.success,
                "summary": result.body,
                "url": result.external_url or result.url,
            }
        )
        completed = list(task_state.get("completed_steps") or [])
        completed.append(
            {
                "step_id": step.step_id,
                "label": step.label,
                "url": result.external_url or result.url,
                "entity_type": result.entity_type,
                "entity_id": result.entity_id,
            }
        )
        params["step_results"] = step_results
        params["current_step_index"] = idx + 1
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
            },
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        if not result.success:
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": f"Step **{step.label}** failed: {result.body}",
                "execution_result": result.__dict__,
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
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "answer",
                    "message": f"Step **{step.label}** failed: {result.body}",
                    "execution_result": result.__dict__,
                    "task_state": task_state,
                }
            step_results = list(params.get("step_results") or [])
            step_results.append(
                {
                    "step_id": step.step_id,
                    "label": step.label,
                    "success": True,
                    "summary": result.body,
                    "url": result.external_url or result.url,
                }
            )
            params["step_results"] = step_results
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
        primary_url = next((str(r.get("url")) for r in reversed(step_results) if r.get("url")), "/ai")

        result = ExecutionResult(
            success=successes > 0,
            entity_type="orchestration",
            entity_id=conversation_id,
            url=primary_url,
            title=f"Orchestration complete ({successes}/{len(step_results)} steps)",
            body=summary_body,
            notification_type="task_completed",
            task_label="Multi-step orchestration complete",
        )
        create_user_notification(
            client,
            org_id=org_id,
            user_id=user_id,
            notification_type=result.notification_type,
            title=result.title,
            body=result.body[:500],
            url=result.url,
            entity_type=result.entity_type,
            entity_id=result.entity_id,
        )
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "completed",
                    "result": result.__dict__,
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
                f"{summary_body}\n\n"
                f"[View results]({primary_url})"
            ),
            "execution_result": result.__dict__,
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
        """Split a single sentence that mentions multiple integrations."""
        text = message.strip()
        integrations = ChatOrchestrationService._mentioned_integrations(text, connected_integrations)
        if len(integrations) < 2:
            return [text]
        segments: list[str] = []
        lowered = text.lower()
        for integration in integrations:
            aliases = INTEGRATION_ALIASES.get(integration, (integration,))
            alias = next((a for a in aliases if a in lowered), integration)
            pattern = re.compile(rf"([^,.;]*\b{re.escape(alias)}\b[^,.;]*)", re.I)
            match = pattern.search(text)
            if match:
                segments.append(match.group(1).strip())
        return segments or [text]

    @staticmethod
    def _mentioned_integrations(message: str, connected_integrations: list[str]) -> list[str]:
        lowered = message.lower()
        connected = {c.lower() for c in connected_integrations}
        found: list[str] = []
        for integration, aliases in INTEGRATION_ALIASES.items():
            if any(alias in lowered for alias in aliases):
                if integration in connected or integration not in found:
                    found.append(integration)
        return list(dict.fromkeys(found))

    @staticmethod
    def _enrich_plan_with_context(
        plan: ConnectorActionPlan,
        prior_results: list[dict[str, Any]],
    ) -> ConnectorActionPlan:
        if not prior_results:
            return plan
        if plan.integration != "slack" or plan.invoke_action != "slack.post_message":
            return plan
        summaries = [str(row.get("summary") or "") for row in prior_results if row.get("summary")]
        if not summaries:
            return plan
        args = dict(plan.args)
        prefix = "Orchestration summary:\n" + "\n".join(f"- {line}" for line in summaries[-3:])
        existing = str(args.get("message") or "").strip()
        args["message"] = f"{existing}\n\n{prefix}".strip() if existing else prefix
        return ConnectorActionPlan(
            tool_name=plan.tool_name,
            invoke_action=plan.invoke_action,
            integration=plan.integration,
            kind=plan.kind,
            label=plan.label,
            args=args,
            requires_approval=plan.requires_approval,
            approval_reason=plan.approval_reason,
            destructive=plan.destructive,
        )


_chat_orchestration_service: ChatOrchestrationService | None = None


def get_chat_orchestration_service(settings: Settings | None = None) -> ChatOrchestrationService:
    global _chat_orchestration_service
    if _chat_orchestration_service is None or settings is not None:
        _chat_orchestration_service = ChatOrchestrationService(settings)
    return _chat_orchestration_service
