"""Post-dialogue task execution for universal and per-agent chat surfaces."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.conversation_state_service import get_conversation_state_service
from app.services.entity_link_service import (
    build_connector_management_url,
    build_entity_url,
    resolve_execution_result_url,
)
from app.services.notification_emitter import emit_notification

logger = get_logger(__name__)

CONFIRM_PATTERN = re.compile(
    r"^\s*(yes|yeah|yep|y|confirm|confirmed|go ahead|proceed|create it|do it|"
    r"sounds good|approved|sure|ok|okay|please do|let's do it|lets do it)\s*[.!]?\s*$",
    re.I,
)
DECLINE_PATTERN = re.compile(
    r"^\s*(no|nope|cancel|stop|not yet|wait|hold on|never mind|nevermind)\s*[.!]?\s*$",
    re.I,
)
QUOTED_NAME = re.compile(r'["\']([^"\']{2,80})["\']')
NAME_PREFIX = re.compile(
    r"^(?:call it|name it|named|it(?:'s| is)|agent name(?: is)?)\s+(.+)$",
    re.I,
)
WORKFLOW_CREATE = re.compile(
    r"\b(create|build|make|set up)\b.*\b(workflow|automation|playbook)\b",
    re.I,
)
AGENT_CREATE = re.compile(
    r"\b(create|build|make|set up)\b.*\bagent\b",
    re.I,
)

PLATFORM_TASK_TYPES = frozenset(
    {"create_agent", "create_workflow", "execute_workflow", "run_agent_task"}
)


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    entity_type: str
    entity_id: str
    title: str
    body: str
    connector_management_url: str | None = None
    result_url: str | None = None
    integration: str | None = None
    notification_type: str = "task_completed"
    task_label: str = ""
    structured: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] | None = None
    error_code: str | None = None
    # Wave 7 — calibrated uncertainty notes for verify/relay UI.
    assumption_notes: list[str] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ExecutionResult:
        data = dict(payload or {})
        if "result_url" not in data and "url" in data:
            legacy_url = data.pop("url")
            if data.get("entity_type") == "connector" and str(legacy_url or "").startswith("/connectors"):
                data.setdefault("connector_management_url", legacy_url)
            else:
                data.setdefault("result_url", legacy_url)
        data.pop("external_url", None)
        allowed = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in allowed})


def _serialize_execution_result(result: ExecutionResult) -> dict[str, Any]:
    from app.services.artifact_registry_service import serialize_execution_result

    return serialize_execution_result(result)


class ConversationalExecutionService:
    """Collects dialogue parameters, confirms, executes platform APIs, and notifies."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._state = get_conversation_state_service(self.settings)

    @staticmethod
    def is_confirmation(message: str) -> bool:
        return bool(CONFIRM_PATTERN.match(message.strip()))

    @staticmethod
    def is_decline(message: str) -> bool:
        return bool(DECLINE_PATTERN.match(message.strip()))

    def resolve_task_type(
        self,
        message: str,
        understanding: dict[str, Any],
        task_state: dict[str, Any],
    ) -> str | None:
        pending = task_state.get("pending_task") or {}
        if isinstance(pending, dict) and pending.get("type"):
            return str(pending["type"])
        if understanding.get("conversational_create"):
            if WORKFLOW_CREATE.search(message):
                return "create_workflow"
            return "create_agent"
        if AGENT_CREATE.search(message):
            return "create_agent"
        if WORKFLOW_CREATE.search(message):
            return "create_workflow"
        clarified = task_state.get("clarified_params") or {}
        if clarified.get("agent_name") or clarified.get("agent_purpose"):
            return "create_agent"
        if clarified.get("workflow_goal") or clarified.get("workflow_trigger"):
            return "create_workflow"
        return None

    def extract_param_updates(
        self,
        message: str,
        task_type: str,
        clarified: dict[str, Any],
    ) -> dict[str, str]:
        text = message.strip()
        if not text or self.is_confirmation(text) or self.is_decline(text):
            return {}
        updates: dict[str, str] = {}
        quoted = QUOTED_NAME.search(text)
        if quoted:
            updates["agent_name" if task_type == "create_agent" else "workflow_goal"] = quoted.group(1).strip()

        name_match = NAME_PREFIX.match(text)
        if name_match and task_type == "create_agent" and not clarified.get("agent_name"):
            updates["agent_name"] = name_match.group(1).strip().rstrip(".")

        if task_type == "create_agent":
            if " for " in text.lower() and not clarified.get("agent_name"):
                name_part, purpose_part = re.split(r"\s+for\s+", text, maxsplit=1, flags=re.I)
                updates["agent_name"] = name_part.strip().strip('"\'')
                updates["agent_purpose"] = purpose_part.strip().rstrip(".")
            elif not clarified.get("agent_name") and len(text.split()) <= 8:
                updates["agent_name"] = text.strip().strip('"\'')
            elif clarified.get("agent_name") and not clarified.get("agent_purpose"):
                updates["agent_purpose"] = text.strip().rstrip(".")
        elif task_type == "create_workflow":
            if not clarified.get("workflow_goal") and len(text.split()) <= 20:
                updates["workflow_goal"] = text.strip().rstrip(".")
            elif clarified.get("workflow_goal") and not clarified.get("workflow_trigger"):
                updates["workflow_trigger"] = text.strip().rstrip(".")
        return {k: v for k, v in updates.items() if v}

    @staticmethod
    def params_ready(task_type: str, clarified: dict[str, Any]) -> bool:
        if task_type == "create_agent":
            return bool(clarified.get("agent_name") and clarified.get("agent_purpose"))
        if task_type == "create_workflow":
            return bool(clarified.get("workflow_goal"))
        if task_type == "execute_workflow":
            return bool(clarified.get("workflow_id") or clarified.get("query"))
        if task_type == "run_agent_task":
            return bool(clarified.get("task") and (clarified.get("agent_id") or clarified.get("agent_name")))
        return False

    def build_confirm_message(self, task_type: str, clarified: dict[str, Any]) -> str:
        if task_type == "create_agent":
            name = str(clarified.get("agent_name") or "your agent")
            purpose = str(clarified.get("agent_purpose") or "general assistance")
            return (
                f"I'll create an agent named **{name}** to help with **{purpose}**.\n\n"
                "Reply **yes** to create it now, or tell me what you'd like to change."
            )
        if task_type == "execute_workflow":
            wf_name = str(clarified.get("workflow_name") or clarified.get("query") or "this workflow")
            wf_id = str(clarified.get("workflow_id") or "").strip()
            id_bit = f" (id `{wf_id}`)" if wf_id else ""
            goal = str(clarified.get("workflow_goal") or "").strip()
            goal_line = f"\nGoal: {goal}" if goal else ""
            return (
                f"I'll **execute** the workflow **{wf_name}**{id_bit}.{goal_line}\n\n"
                "This starts a new run and may trigger connected steps "
                "(connectors, agents, notifications).\n\n"
                "Reply **yes** to run it now, or **no** to cancel."
            )
        if task_type == "run_agent_task":
            agent_name = str(clarified.get("agent_name") or "the agent")
            task = str(clarified.get("task") or "").strip()
            truncated = task if len(task) <= 240 else task[:237] + "..."
            return (
                f"I'll run **{agent_name}** on this task:\n\n> {truncated}\n\n"
                "The agent may use its permitted tools and connected integrations "
                "(including writes).\n\n"
                "Reply **yes** to start, or **no** to cancel."
            )
        goal = str(clarified.get("workflow_goal") or "your workflow")
        trigger = clarified.get("workflow_trigger")
        trigger_line = f" Trigger: **{trigger}**." if trigger else ""
        return (
            f"I'll create a draft workflow for **{goal}**.{trigger_line}\n\n"
            "Reply **yes** to create it now, or tell me what to adjust."
        )

    async def process_turn(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        message: str,
        understanding: dict[str, Any],
        classification: dict[str, Any],
        task_state: dict[str, Any],
        client: Any,
    ) -> dict[str, Any] | None:
        task_type = self.resolve_task_type(message, understanding, task_state)
        if not task_type:
            return None

        clarified = dict(task_state.get("clarified_params") or {})
        # ReAct platform materialize stores params on pending_task — merge so confirm works.
        pending_early = task_state.get("pending_task") if isinstance(task_state.get("pending_task"), dict) else {}
        if pending_early.get("params") and isinstance(pending_early["params"], dict):
            merged = dict(pending_early["params"])
            merged.update(clarified)
            clarified = merged
        updates = self.extract_param_updates(message, task_type, clarified)
        if updates:
            clarified.update(updates)
            await self._state.update_task_state(
                conversation_id,
                org_id,
                {
                    "clarified_params": updates,
                    "pending_task": {"type": task_type, "status": "collecting"},
                },
            )

        if self.is_decline(message):
            await self._state.update_task_state(
                conversation_id,
                org_id,
                {"pending_task": None, "clarified_params": {}},
            )
            if task_type == "execute_workflow":
                decline_msg = "No problem — I won't execute that workflow. Tell me when you'd like to try again."
            elif task_type == "run_agent_task":
                decline_msg = "No problem — I won't run that agent task. Tell me when you'd like to try again."
            else:
                decline_msg = (
                    "No problem — I won't create anything. "
                    "Tell me when you'd like to try again or what you'd prefer instead."
                )
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": decline_msg,
                "task_state": await self._state.get_task_state(conversation_id, org_id, client=client),
            }

        if not self.params_ready(task_type, clarified):
            return None

        awaiting = (task_state.get("pending_task") or {}).get("status") == "awaiting_confirm"
        if self.is_confirmation(message) or awaiting and message.strip().lower() in {"confirm", "create"}:
            execution = await self.execute_task(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                task_type=task_type,
                clarified=clarified,
                client=client,
                classification=classification,
            )
            refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
            if execution.success:
                link = ""
                if execution.result_url:
                    link = f"\n\n[View in Gravitre]({execution.result_url})"
                if task_type == "execute_workflow":
                    done = f"Done — I started **{execution.title}**.\n\n{execution.body}{link}"
                elif task_type == "run_agent_task":
                    done = f"Done — **{execution.title}** finished.\n\n{execution.body}{link}"
                else:
                    done = f"Done — I created **{execution.title}**.\n\n{execution.body}{link}"
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "answer",
                    "message": done,
                    "execution_result": _serialize_execution_result(execution),
                    "task_state": refreshed,
                }
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": f"I couldn't complete that request: {execution.body}",
                "execution_result": _serialize_execution_result(execution),
                "task_state": refreshed,
            }

        await self._state.update_task_state(
            conversation_id,
            org_id,
            {"pending_task": {"type": task_type, "status": "awaiting_confirm", "params": clarified}},
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        return {
            "stop_pipeline": True,
            "dialogue_mode": "confirm",
            "message": self.build_confirm_message(task_type, clarified),
            "task_state": refreshed,
            "pending_task": {"type": task_type, "params": clarified},
        }

    async def execute_confirmed_task(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        client: Any,
        classification: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        task_state = await self._state.get_task_state(conversation_id, org_id, client=client)
        pending = task_state.get("pending_task") or {}
        task_type = str(pending.get("type") or "")
        clarified = dict(task_state.get("clarified_params") or pending.get("params") or {})
        if not task_type or not self.params_ready(task_type, clarified):
            return ExecutionResult(
                success=False,
                entity_type="conversation",
                entity_id=conversation_id,
                result_url="/ai",
                title="Task not ready",
                body="Missing details — continue the conversation to confirm name, purpose, or workflow goal.",
            )
        return await self.execute_task(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            task_type=task_type,
            clarified=clarified,
            client=client,
            classification=classification or {},
        )

    async def execute_task(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        task_type: str,
        clarified: dict[str, Any],
        client: Any,
        classification: dict[str, Any],
    ) -> ExecutionResult:
        try:
            if task_type == "create_agent":
                result = await self._create_agent(org_id, user_id, clarified, client)
            elif task_type == "create_workflow":
                result = await self._create_workflow(org_id, user_id, clarified, client)
            elif task_type == "execute_workflow":
                result = await self._execute_workflow(org_id, user_id, clarified, client)
            elif task_type == "run_agent_task":
                result = await self._run_agent_task(org_id, user_id, clarified, client)
            else:
                return ExecutionResult(
                    success=False,
                    entity_type="unknown",
                    entity_id="",
                    result_url="/ai",
                    title="Unsupported task",
                    body=f"Task type {task_type} is not supported yet.",
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "conversational execute failed org_id=%s task_type=%s error=%s",
                org_id,
                task_type,
                exc,
            )
            return ExecutionResult(
                success=False,
                entity_type=task_type,
                entity_id="",
                result_url="/ai",
                title="Execution failed",
                body=str(exc),
            )

        emit_notification(
            client,
            org_id=org_id,
            user_id=user_id,
            event_type=result.notification_type,
            title=result.title,
            body=result.body,
            entity_ref={
                "entity_type": result.entity_type,
                "entity_id": result.entity_id or None,
                "result_url": result.result_url,
            },
            channel_hints={"bell": True, "email": False},
        )

        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "pending_task": {"type": task_type, "status": "executed", "result": result.__dict__},
                "completed_steps": [
                    {
                        "step_id": f"execute_{task_type}",
                        "label": result.task_label or result.title,
                        "url": result.result_url,
                        "entity_type": result.entity_type,
                        "entity_id": result.entity_id,
                    }
                ],
                "approved_actions": [{"type": task_type, "entity_id": result.entity_id, "url": result.result_url}],
            },
        )

        await self._record_learning_outcome(org_id, user_id, result, classification)
        return result

    async def _create_agent(
        self,
        org_id: str,
        user_id: str,
        clarified: dict[str, Any],
        client: Any,
    ) -> ExecutionResult:
        from app.operators.repository import create_operator
        from app.workflows.audit import write_audit_event

        name = str(clarified.get("agent_name") or "New Agent").strip()[:120]
        purpose = str(clarified.get("agent_purpose") or "").strip()
        invoke_action = "assistant.create_agent"
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user_id or "system",
            action="tool.invoke.requested",
            resource_type="agent",
            resource_id=org_id,
            metadata={"action": invoke_action, "name": name},
        )
        operator = create_operator(
            client,
            org_id,
            {
                "name": name,
                "description": purpose or None,
                "role": str(clarified.get("agent_role") or "assistant"),
                "status": "inactive",
                "capabilities": [],
            },
            user_id,
        )
        agent_id = str(operator["id"])
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user_id or "system",
            action="tool.invoke.completed",
            resource_type="agent",
            resource_id=agent_id,
            metadata={"action": invoke_action, "name": name},
        )
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user_id or "system",
            action="agent.created",
            resource_type="agent",
            resource_id=agent_id,
            metadata={"source": "conversational_execution", "name": name},
        )
        result_url = build_entity_url("agent", agent_id)
        return ExecutionResult(
            success=True,
            entity_type="agent",
            entity_id=agent_id,
            result_url=result_url,
            title=name,
            body=f"Created agent “{name}”" + (f" for {purpose}" if purpose else "") + ". Open the agent page to configure connectors and workflows.",
            notification_type="agent_created",
            task_label=f"Created agent {name}",
        )

    async def _create_workflow(
        self,
        org_id: str,
        user_id: str,
        clarified: dict[str, Any],
        client: Any,
    ) -> ExecutionResult:
        from app.services.assistant_tools import tool_create_workflow

        goal = str(clarified.get("workflow_goal") or "Assistant workflow")
        trigger = str(clarified.get("workflow_trigger") or "")
        query = f"{goal}. Trigger: {trigger}" if trigger else goal
        output = tool_create_workflow(org_id, query, self.settings, user_id=user_id)
        if output.get("error"):
            return ExecutionResult(
                success=False,
                entity_type="workflow",
                entity_id="",
                result_url="/workflows",
                title="Workflow creation failed",
                body=str(output.get("error")),
            )
        workflow_id = str(output.get("id") or "")
        result_url = build_entity_url("workflow", workflow_id)
        name = str(output.get("name") or goal)
        return ExecutionResult(
            success=True,
            entity_type="workflow",
            entity_id=workflow_id,
            result_url=result_url,
            title=name,
            body=f"Created draft workflow “{name}”. Open the builder to add steps and publish.",
            notification_type="workflow_created",
            task_label=f"Created workflow {name}",
        )

    async def _execute_workflow(
        self,
        org_id: str,
        user_id: str,
        clarified: dict[str, Any],
        client: Any,
    ) -> ExecutionResult:
        from app.services.assistant_tools import tool_execute_workflow
        from app.workflows.audit import write_audit_event

        query = str(clarified.get("query") or clarified.get("workflow_name") or "").strip()
        workflow_id = str(clarified.get("workflow_id") or "").strip()
        if workflow_id and workflow_id not in query:
            query = workflow_id
        env = str(clarified.get("environment_name") or "production")
        invoke_action = "assistant.execute_workflow"
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user_id or "system",
            action="tool.invoke.requested",
            resource_type="workflow",
            resource_id=workflow_id or org_id,
            metadata={
                "action": invoke_action,
                "workflow_id": workflow_id or None,
                "workflow_name": clarified.get("workflow_name"),
            },
        )
        output = tool_execute_workflow(
            org_id,
            query,
            self.settings,
            user_id=user_id,
            environment_name=env,
        )
        if output.get("error"):
            write_audit_event(
                client,
                org_id=org_id,
                actor_id=user_id or "system",
                action="tool.invoke.failed",
                resource_type="workflow",
                resource_id=workflow_id or org_id,
                metadata={"action": invoke_action, "error": output.get("error"), "message": output.get("message")},
            )
            return ExecutionResult(
                success=False,
                entity_type="workflow",
                entity_id=workflow_id,
                result_url=build_entity_url("workflow", workflow_id) if workflow_id else "/workflows",
                title="Workflow execution failed",
                body=str(output.get("message") or output.get("error")),
                error_code=str(output.get("error") or "workflow_execute_failed"),
            )
        run_id = str(output.get("runId") or "")
        wf_id = str(output.get("workflowId") or workflow_id)
        wf_name = str(output.get("workflowName") or clarified.get("workflow_name") or "Workflow")
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user_id or "system",
            action="tool.invoke.completed",
            resource_type="workflow",
            resource_id=wf_id or org_id,
            metadata={
                "action": invoke_action,
                "workflow_id": wf_id,
                "run_id": run_id,
                "status": output.get("status"),
            },
        )
        result_url = build_entity_url("workflow_run", run_id) if run_id else build_entity_url("workflow", wf_id)
        return ExecutionResult(
            success=True,
            entity_type="workflow_run",
            entity_id=run_id or wf_id,
            result_url=result_url,
            title=wf_name,
            body=str(output.get("message") or f"Workflow run started for “{wf_name}”."),
            notification_type="workflow_executed",
            task_label=f"Executed workflow {wf_name}",
            structured={"runId": run_id, "workflowId": wf_id, "status": output.get("status")},
        )

    async def _run_agent_task(
        self,
        org_id: str,
        user_id: str,
        clarified: dict[str, Any],
        client: Any,
    ) -> ExecutionResult:
        from app.services.assistant_tools import tool_run_agent_task
        from app.workflows.audit import write_audit_event

        task = str(clarified.get("task") or "").strip()
        agent_id = str(clarified.get("agent_id") or "").strip() or None
        agent_name = str(clarified.get("agent_name") or "Agent")
        invoke_action = "assistant.run_agent_task"
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user_id or "system",
            action="tool.invoke.requested",
            resource_type="agent",
            resource_id=agent_id or org_id,
            metadata={"action": invoke_action, "agent_id": agent_id, "task": task[:200]},
        )
        output = await tool_run_agent_task(
            org_id,
            task,
            self.settings,
            agent_id=agent_id,
            user_id=user_id,
        )
        resolved_id = str(output.get("agentId") or agent_id or "")
        if output.get("error"):
            write_audit_event(
                client,
                org_id=org_id,
                actor_id=user_id or "system",
                action="tool.invoke.failed",
                resource_type="agent",
                resource_id=resolved_id or org_id,
                metadata={"action": invoke_action, "error": output.get("error")},
            )
            return ExecutionResult(
                success=False,
                entity_type="agent",
                entity_id=resolved_id,
                result_url=build_entity_url("agent", resolved_id) if resolved_id else "/agents",
                title="Agent task failed",
                body=str(output.get("error")),
            )
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=user_id or "system",
            action="tool.invoke.completed",
            resource_type="agent",
            resource_id=resolved_id or org_id,
            metadata={
                "action": invoke_action,
                "agent_id": resolved_id,
                "status": output.get("status"),
                "react_trace_steps": output.get("reactTraceSteps"),
            },
        )
        name = str(output.get("agentName") or agent_name)
        out_text = str(output.get("output") or "").strip()
        body = out_text[:500] if out_text else f"Agent “{name}” completed the task."
        return ExecutionResult(
            success=True,
            entity_type="agent",
            entity_id=resolved_id,
            result_url=build_entity_url("agent", resolved_id) if resolved_id else "/agents",
            title=name,
            body=body,
            notification_type="agent_task_completed",
            task_label=f"Ran agent {name}",
            structured={"status": output.get("status"), "output": output.get("output")},
        )

    async def _record_learning_outcome(
        self,
        org_id: str,
        user_id: str,
        result: ExecutionResult,
        classification: dict[str, Any],
    ) -> None:
        try:
            from app.services.intelligence_outcome_coordinator import get_intelligence_outcome_coordinator

            coordinator = get_intelligence_outcome_coordinator(self.settings)
            coordinator.record_response_async(
                org_id,
                agent_id=None,
                message_id=None,
                action_taken={
                    "type": "conversational_execute",
                    "entity_type": result.entity_type,
                    "entity_id": result.entity_id,
                    "action_type": result.notification_type,
                },
                response={
                    "answer": result.body,
                    "success": result.success,
                    "url": result.result_url,
                    "strategy_key": "conversational_execute:v1",
                },
                classification={
                    **classification,
                    "intent": "workflow_planning",
                    "learning_layers": ["v1", "v7", "v8"],
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("learning outcome record skipped: %s", exc)


_conversational_execution_service: ConversationalExecutionService | None = None


def get_conversational_execution_service(
    settings: Settings | None = None,
) -> ConversationalExecutionService:
    global _conversational_execution_service
    if _conversational_execution_service is None or settings is not None:
        _conversational_execution_service = ConversationalExecutionService(settings)
    return _conversational_execution_service
