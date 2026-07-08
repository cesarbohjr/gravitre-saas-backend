"""Governed connector execution from universal chat — NL → catalog → risk → invoke_tool."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

from app.config import Settings, get_settings
from app.connectors.action_catalog.registry import get_vendor_spec
from app.core.logging import get_logger
from app.services.conversation_state_service import get_conversation_state_service
from app.services.conversational_execution_service import (
    CONFIRM_PATTERN,
    DECLINE_PATTERN,
    ExecutionResult,
)
from app.services.entity_link_service import build_connector_management_url
from app.services.notification_service import create_user_notification
from app.services.risk_approval_evaluator import get_risk_approval_evaluator
from app.services.chat_action_mapper import get_chat_action_mapper
from app.services.chat_connector_models import INTEGRATION_ALIASES, ConnectorActionPlan, LIST_CREATE_INTENT
from app.services.tool_registry import get_tool_registry
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext
from app.connectors.connector_availability_service import (
    find_integration_availability,
    format_connector_blocking_message,
    get_connector_availability_service,
)
from app.services.connector_session_state import (
    build_session_summary,
    connector_session_patch,
    load_connector_session,
    record_entity_from_execution,
    record_step_output,
    sync_legacy_resolved_entities,
)

logger = get_logger(__name__)


def _result_link_label(integration: str | None) -> str:
    normalized = str(integration or "").strip()
    if not normalized:
        return "View result"
    return f"View in {normalized[:1].upper()}{normalized[1:]}"

CONNECTOR_MENTION = re.compile(
    r"\b(hubspot|salesforce|slack|zendesk|github|jira|stripe|pagerduty|quickbooks|crm|"
    r"monday|gmail|drive|calendar|figma|canva|intercom|clickup|pipedrive|confluence|teams|"
    r"google|microsoft|notion|asana|apollo|odoo|netsuite|workday)\b",
    re.I,
)
ACTION_VERB = re.compile(
    r"\b(search|find|list|get|lookup|query|show|fetch|create|update|post|send|write|"
    r"close|log|notify|message|assign|enroll|add)\b",
    re.I,
)
QUOTED = re.compile(r'["\']([^"\']{1,500})["\']')
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
TICKET_ID = re.compile(r"\b(?:ticket\s*#?\s*|#)(\d{3,})\b", re.I)
DEAL_ID = re.compile(r"\b(?:deal\s*#?\s*)(\d+)\b", re.I)
GITHUB_REPO = re.compile(r"\b([\w.-]+/[\w.-]+)\b")
SEARCH_FOR = re.compile(
    r"(?:search|find|lookup|list|query|show)\s+(?:for\s+)?(.+?)(?:\s+in\s+\w+|\s*$)",
    re.I,
)
HUBSPOT_LIST_CONTACTS = re.compile(
    r"\b(?:any|all|some|recent)\b.*\bcontacts?\b|\b(?:see|show|list|get|do you see|do you have)\b.*\bcontacts?\b",
    re.I,
)

READ_ACTION_HINTS = frozenset(
    {
        "search",
        "list",
        "get",
        "query",
        "history",
        "pulls.list",
        "issues.search",
        "invoices.list",
        "incidents.list",
        "tickets.get",
        "leads.search",
        "contacts.search",
    },
)


class ChatConnectorExecutionService:
    """Maps chat requests to cataloged connector tools with governed execution."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._state = get_conversation_state_service(self.settings)
        self._registry = get_tool_registry()
        self._availability = get_connector_availability_service(self.settings)

    def _live_connected_integrations(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str = "production",
        action_key: str | None = None,
    ) -> list[str]:
        return self._registry.list_connected_integrations(
            client,
            org_id,
            environment_name,
            force_live=True,
            action_key=action_key,
        )

    @staticmethod
    def _detect_integration(message: str) -> str | None:
        lowered = message.lower()
        for integration, aliases in INTEGRATION_ALIASES.items():
            if any(alias in lowered for alias in aliases):
                return integration
        match = CONNECTOR_MENTION.search(message)
        if not match:
            return None
        token = match.group(1).lower()
        if token == "crm":
            return "hubspot"
        return token

    @staticmethod
    def _infer_intent_summary(message: str) -> str:
        text = message.strip()
        if LIST_CREATE_INTENT.search(text):
            list_match = re.search(
                r"\b(?:list|group|segment)\s+(?:named|called)?\s*[\"']?([^\"'.]+)",
                text,
                re.I,
            )
            label = list_match.group(1).strip() if list_match else "contact list"
            return f"Create contact list ({label[:80]})"
        task_match = re.search(
            r"\bcreate\s+(?:a\s+)?task\s+(?:in\s+asana\s+)?(?:for\s+)?(.+?)(?:[?.!]|$)",
            text,
            re.I,
        )
        if task_match and "asana" in text.lower():
            return "Create Asana task"
        return text[:120]

    @staticmethod
    def _list_chat_actions(integration: str) -> list[str]:
        from app.services.connector_execution_matrix import build_connector_execution_matrix

        actions: list[str] = []
        for entry in build_connector_execution_matrix():
            if entry.connector_id != integration or not entry.chat_executable:
                continue
            actions.append(f"{entry.action_key} — {entry.display_name}")
        return actions[:12]

    def _build_unresolved_turn(
        self,
        *,
        message: str,
        integration: str | None,
        connected_integrations: list[str],
        client: Any,
        org_id: str,
        environment_name: str,
        task_state: dict[str, Any],
    ) -> dict[str, Any]:
        from app.services.connector_action_workflows import format_capability_fallback_message
        from app.services.execution_envelope import (
            build_not_executable,
            format_not_executable_message,
            format_operator_response,
        )

        intent = self._infer_intent_summary(message)
        connected = {c.lower() for c in connected_integrations}

        if integration:
            availability = find_integration_availability(
                client,
                org_id,
                integration,
                self.settings,
                environment_name=environment_name,
                force_live=True,
            )
            vendor_label = integration.replace("_", " ").title()
            if availability is None or not availability.get("execution_available"):
                blocking = format_connector_blocking_message(integration, availability)
                planned = self._planned_details_from_message(message, integration)
                message_text = format_operator_response(
                    intent=intent,
                    status="blocked — connector not ready",
                    missing_connector=vendor_label,
                    planned=planned or None,
                    next_step=f"Connect {vendor_label} at /connectors, then retry this request.",
                    result=blocking,
                )
                payload = build_not_executable(
                    "missing_connector",
                    next_step=f"Connect {vendor_label} at /connectors, then retry.",
                    metadata={
                        "operator_format": True,
                        "intent": intent,
                        "status": "blocked — connector not ready",
                        "missing_connector": vendor_label,
                        "planned": planned,
                        "next_step": f"Connect {vendor_label} at /connectors, then retry.",
                        "result": blocking,
                    },
                )
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "answer",
                    "message": message_text,
                    "not_executable": payload,
                    "task_state": task_state,
                }

            if integration in connected and LIST_CREATE_INTENT.search(message):
                from app.services.connector_capability_analysis import (
                    analyze_capability_gaps,
                    resolve_missing_action,
                )

                available = self._list_chat_actions(integration)
                gaps = analyze_capability_gaps(integration, available)
                planned = self._planned_details_from_message(message, integration)
                if gaps.get("create_list"):
                    list_action = resolve_missing_action(integration, "create_list")
                    message_text = format_operator_response(
                        intent=intent,
                        status="blocked — action not matched",
                        matched_action=list_action,
                        planned=planned or None,
                        available_actions=available,
                        next_step=(
                            f"List creation is available via `{list_action}`. "
                            "Retry with an explicit list name, e.g. "
                            f"\"Create an {vendor_label} list named MSP prospects\"."
                        ),
                    )
                    payload = build_not_executable(
                        "not_implemented",
                        next_step=(
                            f"List creation is available via `{list_action}`. "
                            "Retry with an explicit list name."
                        ),
                        metadata={
                            "operator_format": True,
                            "intent": intent,
                            "status": "blocked — action not matched",
                            "matched_action": list_action,
                            "available_actions": available,
                            "planned": planned,
                        },
                    )
                else:
                    missing_action = resolve_missing_action(integration, "create_list")
                    message_text = format_capability_fallback_message(
                        integration=integration,
                        intent=intent,
                        missing_action=missing_action,
                        available_actions=available,
                        planned=planned or None,
                    )
                    payload = build_not_executable(
                        "unsupported_action",
                        next_step=(
                            f"The {vendor_label} connector has no list/group creation action yet. "
                            f"Recommended implementation: `{missing_action}`."
                        ),
                        metadata={
                            "operator_format": True,
                            "intent": intent,
                            "status": "blocked — action not in catalog",
                            "missing_action": missing_action,
                            "available_actions": available,
                            "planned": planned,
                        },
                    )
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": "answer",
                    "message": message_text,
                    "not_executable": payload,
                    "task_state": task_state,
                }

            available = self._list_chat_actions(integration)
            message_text = format_operator_response(
                intent=intent,
                status="blocked — no matching catalog action",
                available_actions=available,
                next_step="Name the integration action explicitly (e.g. search Apollo companies).",
            )
            payload = build_not_executable(
                "not_implemented",
                next_step="Name the integration action explicitly (e.g. search Apollo companies).",
                metadata={
                    "operator_format": True,
                    "intent": intent,
                    "status": "blocked — no matching catalog action",
                    "available_actions": available,
                    "next_step": "Name the integration action explicitly (e.g. search Apollo companies).",
                },
            )
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": message_text,
                "not_executable": payload,
                "task_state": task_state,
            }

        if not connected_integrations:
            payload = build_not_executable(
                "missing_connector",
                next_step="Connect an integration under Connectors, then retry.",
                metadata={
                    "operator_format": True,
                    "intent": intent,
                    "status": "blocked — no connected integrations",
                    "next_step": "Connect an integration under Connectors, then retry.",
                },
            )
        else:
            mentioned = get_chat_action_mapper()._mentioned_integrations(message, connected_integrations)
            available = self._list_chat_actions(mentioned[0]) if mentioned else []
            payload = build_not_executable(
                "not_implemented",
                next_step="Name the integration and action explicitly (e.g. search HubSpot contacts).",
                metadata={
                    "operator_format": True,
                    "intent": intent,
                    "status": "blocked — no matching catalog action",
                    "available_actions": available,
                    "next_step": "Name the integration and action explicitly (e.g. search HubSpot contacts).",
                },
            )
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": format_not_executable_message(payload),
            "not_executable": payload,
            "task_state": task_state,
        }

    @staticmethod
    def _planned_details_from_message(message: str, integration: str) -> dict[str, str]:
        text = message.strip()
        planned: dict[str, str] = {}
        if integration == "asana":
            for_person = re.search(
                r"\bfor\s+(\w+)\s+to\s+(.+?)(?:\s+by\s+(\w+))?(?:[?.!]|$)",
                text,
                re.I,
            )
            if for_person:
                planned["Assignee"] = for_person.group(1).strip()
                planned["Task"] = for_person.group(2).strip()
                if for_person.group(3):
                    planned["Due"] = for_person.group(3).strip()
        if LIST_CREATE_INTENT.search(text):
            list_match = re.search(
                r"\b(?:list|group)\s+(?:for|named|called)?\s*[\"']?([^\"'.]+)",
                text,
                re.I,
            )
            if list_match:
                planned["List name"] = list_match.group(1).strip()[:80]
            elif "msp" in text.lower():
                planned["List name"] = "MSP Prospects"
        return planned

    def _verify_plan_executable(
        self,
        client: Any,
        org_id: str,
        plan: ConnectorActionPlan,
        *,
        environment_name: str = "production",
    ) -> str | None:
        availability = find_integration_availability(
            client,
            org_id,
            plan.integration,
            self.settings,
            environment_name=environment_name,
            force_live=True,
            action_key=plan.invoke_action,
        )
        if availability and availability.get("execution_available"):
            return None
        return format_connector_blocking_message(
            plan.integration,
            availability,
            action_key=plan.invoke_action,
        )

    def _prefer_static_tool_name(self, registry_key: str, integration: str) -> str | None:
        """Prefer curated static ToolRegistry names when they map to the same invoke action."""
        return self._registry.preferred_static_tool_name(registry_key, integration)

    @staticmethod
    def is_connector_intent(message: str, task_state: dict[str, Any]) -> bool:
        pending = task_state.get("pending_task") or {}
        pending_type = str(pending.get("type") or "")
        if pending_type == "connector_orchestration":
            return False
        if pending_type == "connector_action":
            return True
        text = message.strip()
        if not text or len(text) < 8:
            return False
        lowered = text.lower()
        if any(
            alias in lowered
            for aliases in INTEGRATION_ALIASES.values()
            for alias in aliases
        ) or CONNECTOR_MENTION.search(text):
            return bool(ACTION_VERB.search(text))
        return False

    def plan_action(
        self,
        message: str,
        *,
        connected_integrations: list[str],
        task_state: dict[str, Any],
    ) -> ConnectorActionPlan | None:
        pending = task_state.get("pending_task") or {}
        if isinstance(pending, dict) and pending.get("type") == "connector_action":
            params = dict(pending.get("params") or task_state.get("clarified_params") or {})
            tool_name = str(params.get("tool_name") or "")
            spec = self._registry.get_spec(tool_name)
            if not spec:
                return None
            return ConnectorActionPlan(
                tool_name=tool_name,
                invoke_action=str(params.get("invoke_action") or spec.invoke_action),
                integration=str(params.get("integration") or spec.integration),
                kind=str(params.get("kind") or "write"),
                label=str(params.get("label") or tool_name),
                args=dict(params.get("args") or {}),
                requires_approval=bool(params.get("requires_approval")),
                approval_reason=params.get("approval_reason"),
                destructive=bool(params.get("destructive")),
            )

        mapper = get_chat_action_mapper()
        match = mapper.match_segment(message, connected_integrations=connected_integrations)
        if match:
            kind = match.entry.kind
            tool_name = self._prefer_static_tool_name(
                match.entry.registry_key,
                match.entry.connector_id,
            ) or match.tool_name
            return ConnectorActionPlan(
                tool_name=tool_name,
                invoke_action=match.entry.registry_key,
                integration=match.entry.connector_id,
                kind=kind,
                label=match.entry.display_name,
                args=match.args,
                destructive=match.entry.destructive,
            )

        connected = {c.lower() for c in connected_integrations}
        registered = set(list_registered_actions())
        best: tuple[int, ConnectorActionPlan] | None = None
        for tool_name in self._registry.list_tool_names():
            spec = self._registry.get_spec(tool_name)
            if not spec or spec.always_available or spec.name.startswith("assistant_"):
                continue
            if spec.integration not in connected:
                continue
            score = self._score_tool(message, spec)
            if score <= 0:
                continue
            args = self._extract_args(message, spec)
            if args is None:
                continue
            invoke_action = spec.invoke_action
            if spec.name == "salesforce_update_record":
                invoke_action = self._registry.resolve_invoke_action(spec, args)
            if invoke_action not in registered:
                continue
            kind, destructive = self._catalog_metadata(invoke_action, spec.integration)
            label = self._human_label(spec, args)
            plan = ConnectorActionPlan(
                tool_name=spec.name,
                invoke_action=invoke_action,
                integration=spec.integration,
                kind=kind,
                label=label,
                args=args,
                destructive=destructive,
            )
            if best is None or score > best[0]:
                best = (score, plan)
        return best[1] if best else None

    def plan_fallback_segment(
        self,
        segment: str,
        *,
        connected_integrations: list[str],
    ) -> ConnectorActionPlan | None:
        """Best-effort single-segment plan when strict NL matching fails."""
        match = get_chat_action_mapper().match_segment(segment, connected_integrations=connected_integrations)
        if match:
            tool_name = self._prefer_static_tool_name(
                match.entry.registry_key,
                match.entry.connector_id,
            ) or match.tool_name
            return ConnectorActionPlan(
                tool_name=tool_name,
                invoke_action=match.entry.registry_key,
                integration=match.entry.connector_id,
                kind=match.entry.kind,
                label=match.entry.display_name,
                args=match.args,
                destructive=match.entry.destructive,
            )
        connected = {c.lower() for c in connected_integrations}
        text = segment.strip()
        lowered = text.lower()
        query = self._search_query(text) or text[:120]

        if ("hubspot" in lowered or "crm" in lowered) and "hubspot" in connected:
            spec = self._registry.get_spec("hubspot_search_contacts")
            if spec and "hubspot.contacts.search" in set(list_registered_actions()):
                if HUBSPOT_LIST_CONTACTS.search(text):
                    args = {"list_all": True, "limit": 10}
                    label = "List HubSpot contacts"
                else:
                    args = {"query": query, "limit": 10}
                    label = f"Search HubSpot for “{query[:60]}”"
                return ConnectorActionPlan(
                    tool_name="hubspot_search_contacts",
                    invoke_action="hubspot.contacts.search",
                    integration="hubspot",
                    kind="read",
                    label=label,
                    args=args,
                )
        if "salesforce" in lowered and "salesforce" in connected:
            args = self._extract_args(text, self._registry.get_spec("salesforce_query"))
            if args:
                return ConnectorActionPlan(
                    tool_name="salesforce_query",
                    invoke_action="salesforce.leads.search",
                    integration="salesforce",
                    kind="read",
                    label="Query Salesforce",
                    args=args,
                )
        if "slack" in lowered and "slack" in connected:
            spec = self._registry.get_spec("slack_send_message")
            if spec:
                args = self._extract_args(text, spec)
                if args:
                    kind, destructive = self._catalog_metadata(spec.invoke_action, spec.integration)
                    return ConnectorActionPlan(
                        tool_name=spec.name,
                        invoke_action=spec.invoke_action,
                        integration=spec.integration,
                        kind=kind,
                        label=self._human_label(spec, args),
                        args=args,
                        destructive=destructive,
                    )
        if "zendesk" in lowered and "zendesk" in connected:
            spec = self._registry.get_spec("zendesk_get_ticket")
            if spec:
                args = self._extract_args(text, spec)
                if args:
                    return ConnectorActionPlan(
                        tool_name=spec.name,
                        invoke_action=spec.invoke_action,
                        integration=spec.integration,
                        kind="read",
                        label=f"Get Zendesk ticket #{args.get('ticket_id')}",
                        args=args,
                    )
        return None

    @staticmethod
    def plan_to_dict(plan: ConnectorActionPlan) -> dict[str, Any]:
        return {
            "tool_name": plan.tool_name,
            "invoke_action": plan.invoke_action,
            "integration": plan.integration,
            "kind": plan.kind,
            "label": plan.label,
            "args": dict(plan.args),
            "requires_approval": plan.requires_approval,
            "approval_reason": plan.approval_reason,
            "destructive": plan.destructive,
            "inferred_fields": list(plan.inferred_fields),
            "inference_sources": dict(plan.inference_sources),
        }

    @staticmethod
    def plan_from_dict(payload: dict[str, Any]) -> ConnectorActionPlan:
        inferred = payload.get("inferred_fields") or []
        return ConnectorActionPlan(
            tool_name=str(payload.get("tool_name") or ""),
            invoke_action=str(payload.get("invoke_action") or ""),
            integration=str(payload.get("integration") or ""),
            kind=str(payload.get("kind") or "write"),
            label=str(payload.get("label") or ""),
            args=dict(payload.get("args") or {}),
            requires_approval=bool(payload.get("requires_approval")),
            approval_reason=payload.get("approval_reason"),
            destructive=bool(payload.get("destructive")),
            inferred_fields=tuple(str(item) for item in inferred),
            inference_sources=dict(payload.get("inference_sources") or {}),
        )

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
        if not self.is_connector_intent(message, task_state):
            return None

        connected_integrations = self._live_connected_integrations(
            client,
            org_id,
            environment_name=environment_name,
        )

        plan = self.plan_action(
            message,
            connected_integrations=connected_integrations,
            task_state=task_state,
        )
        if not plan:
            if self.is_connector_intent(message, task_state):
                integration = self._detect_integration(message)
                if integration:
                    availability = find_integration_availability(
                        client,
                        org_id,
                        integration,
                        self.settings,
                        environment_name=environment_name,
                        force_live=True,
                        action_key="hubspot.contacts.search"
                        if integration == "hubspot" and "contact" in message.lower()
                        else None,
                    )
                    if availability is not None and not availability.get("execution_available"):
                        from app.services.execution_envelope import format_operator_response

                        intent = self._infer_intent_summary(message)
                        blocking = format_connector_blocking_message(
                            integration,
                            availability,
                            action_key="hubspot.contacts.search"
                            if integration == "hubspot" and "contact" in message.lower()
                            else None,
                        )
                        return {
                            "stop_pipeline": True,
                            "dialogue_mode": "answer",
                            "message": format_operator_response(
                                intent=intent,
                                status="blocked — connector not ready",
                                missing_connector=integration.replace("_", " ").title(),
                                result=blocking,
                                next_step=blocking,
                            ),
                            "task_state": task_state,
                        }
                return self._build_unresolved_turn(
                    message=message,
                    integration=integration,
                    connected_integrations=connected_integrations,
                    client=client,
                    org_id=org_id,
                    environment_name=environment_name,
                    task_state=task_state,
                )
            return None

        blocked = self._verify_plan_executable(
            client,
            org_id,
            plan,
            environment_name=environment_name,
        )
        if blocked:
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": blocked,
                "task_state": task_state,
            }

        from app.services.connector_action_workflows import (
            format_write_approval_message,
            resolve_assignee_disambiguation,
            validate_connector_plan,
        )
        from app.services.connector_parameter_inference import (
            ParameterInferenceContext,
            infer_missing_parameters,
        )

        inference_context = ParameterInferenceContext(
            message=message,
            conversation_history=list((task_state or {}).get("recent_user_messages") or []),
            task_state=task_state,
            connector_session=load_connector_session(task_state),
            client=client,
            org_id=org_id,
            settings=self.settings,
            environment_name=environment_name,
        )
        plan = infer_missing_parameters(plan, inference_context)

        clarification = validate_connector_plan(plan, message)
        if clarification:
            return {
                "stop_pipeline": True,
                "dialogue_mode": clarification.dialogue_mode,
                "message": clarification.message,
                "task_state": task_state,
                "workflow_status": clarification.status,
            }

        assignee_check = await resolve_assignee_disambiguation(
            client=client,
            org_id=org_id,
            plan=plan,
            settings=self.settings,
            environment_name=environment_name,
        )
        if assignee_check:
            if assignee_check.updated_plan is not None:
                plan = assignee_check.updated_plan
            elif assignee_check.candidates:
                return {
                    "stop_pipeline": True,
                    "dialogue_mode": assignee_check.dialogue_mode,
                    "message": assignee_check.message,
                    "task_state": task_state,
                    "workflow_status": assignee_check.status,
                }

        risk = await self._evaluate_risk(org_id, user_id, plan, classification)
        plan = replace(
            plan,
            requires_approval=bool(risk.get("requires_approval") or plan.kind == "write"),
            approval_reason=risk.get("approval_reason"),
        )

        pending_params = {
            "tool_name": plan.tool_name,
            "invoke_action": plan.invoke_action,
            "integration": plan.integration,
            "kind": plan.kind,
            "label": plan.label,
            "args": plan.args,
            "requires_approval": plan.requires_approval,
            "approval_reason": plan.approval_reason,
            "destructive": plan.destructive,
        }

        if DECLINE_PATTERN.match(message.strip()):
            await self._state.update_task_state(
                conversation_id,
                org_id,
                {"pending_task": None, "clarified_params": {}},
            )
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": "Cancelled — I won't run that connector action. Tell me if you'd like something else.",
                "task_state": await self._state.get_task_state(conversation_id, org_id, client=client),
            }

        awaiting = (task_state.get("pending_task") or {}).get("status") == "awaiting_confirm"
        confirmed = CONFIRM_PATTERN.match(message.strip()) or (
            awaiting and message.strip().lower() in {"confirm", "run", "execute"}
        )

        if confirmed and plan.requires_approval:
            execution = await self.execute_plan(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                plan=plan,
                client=client,
                classification=classification,
                environment_name=environment_name,
            )
            refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
            return self._turn_from_execution(execution, refreshed)

        if not plan.requires_approval:
            execution = await self.execute_plan(
                org_id=org_id,
                user_id=user_id,
                conversation_id=conversation_id,
                plan=plan,
                client=client,
                classification=classification,
                environment_name=environment_name,
            )
            refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
            return self._turn_from_execution(execution, refreshed)

        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "clarified_params": pending_params,
                "pending_task": {
                    "type": "connector_action",
                    "status": "awaiting_confirm",
                    "params": pending_params,
                },
                **self._session_updates_for_pending(task_state, plan),
            },
        )
        refreshed = await self._state.get_task_state(conversation_id, org_id, client=client)
        return {
            "stop_pipeline": True,
            "dialogue_mode": "confirm",
            "message": format_write_approval_message(plan),
            "task_state": refreshed,
            "pending_task": {"type": "connector_action", "params": pending_params},
        }

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
        if str(pending.get("type") or "") != "connector_action":
            return ExecutionResult(
                success=False,
                entity_type="conversation",
                entity_id=conversation_id,
                result_url="/ai",
                title="No connector task",
                body="No pending connector action to execute.",
            )
        plan = self.plan_action("", connected_integrations=[], task_state=task_state)
        if not plan:
            return ExecutionResult(
                success=False,
                entity_type="connector",
                entity_id="",
                connector_management_url="/connectors",
                title="Task not ready",
                body="Missing connector action details.",
            )
        return await self.execute_plan(
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            plan=plan,
            client=client,
            classification=classification or {},
            environment_name=environment_name,
        )

    async def execute_plan(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        plan: ConnectorActionPlan,
        client: Any,
        classification: dict[str, Any],
        environment_name: str = "production",
    ) -> ExecutionResult:
        ctx = ToolContext(
            settings=self.settings,
            client=client,
            org_id=org_id,
            actor_id=user_id,
            environment_name=environment_name,
        )
        try:
            observation = await self._registry.execute_tool(
                ctx=ctx,
                tool_name=plan.tool_name,
                args=plan.args,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "chat connector execute failed org_id=%s action=%s error=%s",
                org_id,
                plan.invoke_action,
                exc,
            )
            return ExecutionResult(
                success=False,
                entity_type="connector",
                entity_id="",
                connector_management_url="/connectors",
                title=plan.label,
                body=str(exc),
                integration=plan.integration,
                task_label=plan.label,
            )

        success = bool(observation.get("success"))
        connector_id = str(observation.get("connector_id") or "")
        result_data = observation.get("result") if isinstance(observation.get("result"), dict) else {}
        external_url = self._external_url(plan.integration, plan.invoke_action, result_data, observation)
        connector_management_url = build_connector_management_url(connector_id)
        result_url = external_url

        if not success:
            return ExecutionResult(
                success=False,
                entity_type="connector",
                entity_id=connector_id,
                connector_management_url=connector_management_url,
                result_url=result_url,
                integration=plan.integration,
                title=plan.label,
                body=str(observation.get("error") or "Connector action failed."),
                task_label=plan.label,
            )

        summary = self._summarize_result(plan, result_data, observation)
        result = ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id=connector_id,
            connector_management_url=connector_management_url,
            result_url=result_url,
            integration=plan.integration,
            title=plan.label,
            body=summary,
            notification_type="task_completed",
            task_label=plan.label,
            structured=result_data,
        )

        create_user_notification(
            client,
            org_id=org_id,
            user_id=user_id,
            notification_type=result.notification_type,
            title=result.title,
            body=result.body,
            url=result.result_url,
            entity_type=result.entity_type,
            entity_id=result.entity_id or None,
        )

        prior_state = await self._state.get_task_state(conversation_id, org_id, client=client)
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "pending_task": {
                    "type": "connector_action",
                    "status": "executed",
                    "result": result.__dict__,
                },
                "completed_steps": [
                    {
                        "step_id": f"connector_{plan.invoke_action}",
                        "label": plan.label,
                        "url": result.result_url,
                        "entity_type": "connector",
                        "entity_id": connector_id,
                    }
                ],
                "approved_actions": [
                    {
                        "type": plan.invoke_action,
                        "tool_name": plan.tool_name,
                        "entity_id": connector_id,
                        "url": result.result_url,
                    }
                ],
                **self._session_updates_after_execution(
                    prior_state,
                    plan,
                    result,
                    result_data,
                ),
            },
        )
        await self._record_outcomes(org_id, user_id, plan, result, observation, classification)
        return result

    def _turn_from_execution(
        self,
        execution: ExecutionResult,
        task_state: dict[str, Any],
    ) -> dict[str, Any]:
        if execution.success:
            link_line = ""
            if execution.result_url:
                label = _result_link_label(execution.integration)
                link_line = f"\n\n[{label}]({execution.result_url})"
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": f"Done — **{execution.title}**.\n\n{execution.body}{link_line}",
                "execution_result": execution.__dict__,
                "task_state": task_state,
            }
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": f"I couldn't complete that: {execution.body}",
            "execution_result": execution.__dict__,
            "task_state": task_state,
        }

    async def _evaluate_risk(
        self,
        org_id: str,
        user_id: str,
        plan: ConnectorActionPlan,
        classification: dict[str, Any],
    ) -> dict[str, Any]:
        evaluator = get_risk_approval_evaluator(self.settings)
        action_payload = {
            "type": plan.invoke_action,
            "estimated_impact": "medium" if plan.kind == "write" else "low",
            "is_destructive": plan.destructive,
            "is_customer_facing": plan.integration in {"slack", "zendesk", "salesforce", "hubspot"},
        }
        merged_classification = {
            **classification,
            "risk_level": "high" if plan.destructive else classification.get("risk_level", "low"),
            "requires_approval": plan.kind == "write" or plan.destructive,
        }
        return await evaluator.evaluate(
            org_id,
            user_id,
            action_payload,
            merged_classification,
            {},
        )

    def _score_tool(self, message: str, spec: Any) -> int:
        text = message.lower()
        score = 0
        aliases = INTEGRATION_ALIASES.get(spec.integration, (spec.integration,))
        if not any(alias in text for alias in aliases):
            return 0
        score += 12
        action_tail = spec.invoke_action.split(".")[-1]
        if any(hint in spec.invoke_action or hint in action_tail for hint in READ_ACTION_HINTS):
            if re.search(r"\b(search|find|list|get|lookup|query|show|fetch)\b", text):
                score += 10
        if re.search(r"\b(create|update|post|send|write|close|log|notify|message)\b", text):
            if "write" in spec.description.lower() or "create" in spec.description.lower() or "send" in spec.description.lower():
                score += 10
        if spec.name.replace("_", " ") in text:
            score += 6
        if spec.integration in text:
            score += 4
        if "slack" in text and spec.integration == "slack" and "message" in text:
            score += 8
        if "hubspot" in text or "crm" in text:
            if "contact" in text and "contact" in spec.name:
                score += 6
            if "deal" in text and "deal" in spec.name:
                score += 6
        if "zendesk" in text and "ticket" in text and "ticket" in spec.name:
            score += 8
        return score

    def _extract_args(self, message: str, spec: Any) -> dict[str, Any] | None:
        name = spec.name
        quoted = [m.group(1).strip() for m in QUOTED.finditer(message)]
        try:
            if name == "hubspot_search_contacts":
                if HUBSPOT_LIST_CONTACTS.search(message):
                    return {"list_all": True, "limit": 10}
                query = self._search_query(message) or (quoted[0] if quoted else None)
                if not query:
                    return None
                return {"query": query, "limit": 10}
            if name == "hubspot_create_contact":
                args: dict[str, Any] = {}
                email = EMAIL.search(message)
                if email:
                    args["email"] = email.group(0)
                if quoted:
                    parts = quoted[0].split()
                    if len(parts) >= 2:
                        args["firstname"], args["lastname"] = parts[0], parts[-1]
                    elif "firstname" not in args:
                        args["firstname"] = quoted[0]
                if not args.get("email") and not args.get("firstname"):
                    return None
                return args
            if name == "hubspot_update_deal":
                deal = DEAL_ID.search(message)
                if not deal:
                    return None
                props: dict[str, Any] = {}
                if quoted:
                    props["dealstage"] = quoted[0]
                stage_match = re.search(r"\bstage\s+(?:to\s+)?([\w\s-]+)", message, re.I)
                if stage_match:
                    props["dealstage"] = stage_match.group(1).strip()
                if not props:
                    return None
                return {"deal_id": deal.group(1), "properties": props, "stage": props.get("dealstage")}
            if name == "hubspot_log_activity":
                body = quoted[0] if quoted else None
                if not body and "log" in message.lower():
                    body = re.sub(r"^.*\blog\b", "", message, flags=re.I).strip(" :.-")
                if not body:
                    return None
                return {"body": body[:2000]}
            if name == "salesforce_query":
                soql_match = re.search(r"\bSELECT\b.+", message, re.I | re.DOTALL)
                if soql_match:
                    return {"soql": soql_match.group(0).strip()}
                query = self._search_query(message)
                if not query:
                    return None
                return {
                    "soql": f"SELECT Id, Name, Email FROM Lead WHERE Name LIKE '%{query[:80]}%' LIMIT 10"
                }
            if name == "slack_send_message":
                channel_match = re.search(r"(#[\w-]+|<#[^>]+>|@\w+)", message)
                channel = channel_match.group(1) if channel_match else None
                message_text = quoted[-1] if len(quoted) >= 2 else (quoted[0] if quoted else None)
                if not message_text:
                    post_match = re.search(
                        r"(?:post|send|message)\s+(?:to\s+)?(?:#[\w-]+|<#[^>]+>|@\w+|\w[\w-]*)\s*[:\-]?\s*(.+)$",
                        message,
                        re.I,
                    )
                    if post_match:
                        message_text = post_match.group(1).strip()
                if not channel or not message_text:
                    return None
                clean_channel = channel.lstrip("#").replace("<", "").replace(">", "")
                if clean_channel.startswith("#"):
                    clean_channel = clean_channel[1:]
                return {"channel": clean_channel, "message": message_text}
            if name == "github_create_issue":
                repo = GITHUB_REPO.search(message)
                title = quoted[0] if quoted else None
                if not repo or not title:
                    return None
                body = quoted[1] if len(quoted) > 1 else None
                payload: dict[str, Any] = {"repo": repo.group(1), "title": title}
                if body:
                    payload["body"] = body
                return payload
            if name == "github_search_issues":
                repo = GITHUB_REPO.search(message)
                if not repo:
                    return None
                return {"repo": repo.group(1), "limit": 10}
            if name == "jira_create_ticket":
                summary = quoted[0] if quoted else None
                project_match = re.search(r"\bproject\s+([\w-]+)\b", message, re.I)
                if not summary or not project_match:
                    return None
                return {"project": project_match.group(1), "summary": summary}
            if name == "jira_search_issues":
                jql_match = re.search(r"\b(?:jql|query)\s+(.+)$", message, re.I)
                if jql_match:
                    return {"jql": jql_match.group(1).strip()}
                query = self._search_query(message)
                if not query:
                    return None
                return {"jql": f'text ~ "{query[:80]}"'}
            if name == "zendesk_get_ticket":
                ticket = TICKET_ID.search(message)
                if not ticket:
                    return None
                return {"ticket_id": ticket.group(1)}
            if name == "zendesk_update_ticket":
                ticket = TICKET_ID.search(message)
                if not ticket:
                    return None
                payload = {"ticket_id": ticket.group(1)}
                if quoted:
                    payload["comment"] = quoted[0]
                status_match = re.search(r"\b(close|open|pending|solved)\b", message, re.I)
                if status_match:
                    payload["status"] = status_match.group(1).lower()
                if len(payload) <= 1:
                    return None
                return payload
        except (TypeError, ValueError):
            return None
        return None

    @staticmethod
    def _search_query(message: str) -> str | None:
        match = SEARCH_FOR.search(message.strip())
        if match:
            return match.group(1).strip(" .\"'")
        return None

    @staticmethod
    def _catalog_metadata(invoke_action: str, integration: str) -> tuple[str, bool]:
        spec = get_vendor_spec(integration)
        if spec:
            for action in spec.all_actions():
                if action.id == invoke_action:
                    return action.kind, action.destructive
        if any(h in invoke_action for h in READ_ACTION_HINTS):
            return "read", False
        return "write", True

    @staticmethod
    def _human_label(spec: Any, args: dict[str, Any]) -> str:
        if spec.name == "slack_send_message":
            return f"Post to Slack #{args.get('channel', 'channel')}"
        if spec.name == "hubspot_search_contacts":
            return f"Search HubSpot for “{args.get('query', '')}”"
        if spec.name == "hubspot_create_contact":
            return f"Create HubSpot contact ({args.get('email') or args.get('firstname', 'contact')})"
        if spec.name == "zendesk_update_ticket":
            return f"Update Zendesk ticket #{args.get('ticket_id')}"
        return spec.description.split(".")[0][:80]

    @staticmethod
    def _external_url(
        integration: str,
        invoke_action: str,
        result_data: dict[str, Any],
        observation: dict[str, Any],
    ) -> str | None:
        candidates: list[Any] = [result_data, observation.get("result")]
        for container in candidates:
            if not isinstance(container, dict):
                continue
            for key in ("url", "html_url", "link", "permalink", "web_url"):
                value = container.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return value
            for nested_key in ("contact", "deal", "issue", "ticket", "data", "message"):
                nested = container.get(nested_key)
                if isinstance(nested, dict):
                    for key in ("url", "html_url", "link", "permalink"):
                        value = nested.get(key)
                        if isinstance(value, str) and value.startswith(("http://", "https://")):
                            return value
                    if nested_key == "issue" and nested.get("html_url"):
                        return str(nested["html_url"])
        if integration == "github" and isinstance(result_data.get("issue"), dict):
            url = result_data["issue"].get("html_url")
            if url:
                return str(url)
        return None

    @staticmethod
    def _session_updates_for_pending(
        task_state: dict[str, Any],
        plan: ConnectorActionPlan,
    ) -> dict[str, Any]:
        session = load_connector_session(task_state)
        session = replace(
            session,
            pending_approval={
                "invokeAction": plan.invoke_action,
                "integration": plan.integration,
                "label": plan.label,
                "args": dict(plan.args or {}),
                "status": "awaiting_confirm",
            },
            session_summary=build_session_summary(
                completed_steps=list(task_state.get("completed_steps") or []),
                step_outputs=session.step_outputs,
                active_entities=session.active_entities,
            ),
        )
        return {
            **connector_session_patch(session),
            "resolved_entities": sync_legacy_resolved_entities(session),
        }

    @staticmethod
    def _session_updates_after_execution(
        task_state: dict[str, Any],
        plan: ConnectorActionPlan,
        result: ExecutionResult,
        structured: dict[str, Any],
    ) -> dict[str, Any]:
        session = load_connector_session(task_state)
        step_id = f"connector_{plan.invoke_action}"
        session = record_step_output(
            session,
            step_id=step_id,
            invoke_action=plan.invoke_action,
            label=plan.label,
            success=result.success,
            summary=result.body,
            url=result.result_url,
            structured=structured,
        )
        if result.success:
            session = record_entity_from_execution(
                session,
                integration=plan.integration,
                invoke_action=plan.invoke_action,
                entity_id=result.entity_id or None,
                structured=structured,
                label=plan.label,
            )
        completed = list(task_state.get("completed_steps") or [])
        completed.append(
            {
                "step_id": step_id,
                "label": plan.label,
                "url": result.result_url,
            }
        )
        session = replace(
            session,
            pending_approval=None,
            session_summary=build_session_summary(
                completed_steps=completed,
                step_outputs=session.step_outputs,
                active_entities=session.active_entities,
            ),
        )
        return {
            **connector_session_patch(session),
            "resolved_entities": sync_legacy_resolved_entities(session),
        }

    @staticmethod
    def _summarize_result(
        plan: ConnectorActionPlan,
        result_data: dict[str, Any],
        observation: dict[str, Any],
    ) -> str:
        if plan.kind == "read":
            contacts = result_data.get("contacts")
            if contacts is None and isinstance(result_data.get("search"), dict):
                raw = result_data["search"].get("results") or []
                contacts = raw if isinstance(raw, list) else None
            if contacts is not None:
                count = len(contacts)
                if count == 0:
                    return "No HubSpot contacts matched that request."
                sample = contacts[0]
                if isinstance(sample, dict):
                    props = sample.get("properties") or sample
                    name_bits = [
                        str(props.get("firstname") or "").strip(),
                        str(props.get("lastname") or "").strip(),
                    ]
                    name = " ".join(bit for bit in name_bits if bit) or str(props.get("email") or "contact")
                    if count == 1:
                        return f"Found 1 HubSpot contact: {name}."
                return f"Found {count} HubSpot contact(s)."
            if "records" in result_data:
                count = len(result_data.get("records") or [])
                return f"Salesforce returned {count} record(s)."
            if "channels" in result_data:
                count = len(result_data.get("channels") or [])
                return f"Listed {count} Slack channel(s)."
            if "ticket" in result_data:
                ticket = result_data["ticket"]
                if isinstance(ticket, dict):
                    return f"Zendesk ticket #{ticket.get('id', '')} — {ticket.get('subject', 'loaded')}."
        if plan.invoke_action == "slack.post_message":
            channel = (result_data or {}).get("channel") or plan.args.get("channel")
            return f"Message posted to Slack #{channel}."
        if plan.integration == "apollo" and plan.invoke_action == "apollo.lists.create":
            label_data = result_data.get("label")
            if isinstance(label_data, dict):
                name = label_data.get("name") or plan.args.get("name")
                list_id = label_data.get("id") or label_data.get("_id")
                if name and list_id:
                    return f'Created contact list "{name}" (id: {list_id}).'
                if name:
                    return f'Created contact list "{name}".'
            name = plan.args.get("name")
            if name:
                return f'Created contact list "{name}".'
        return f"Completed {plan.invoke_action}."

    async def _record_outcomes(
        self,
        org_id: str,
        user_id: str,
        plan: ConnectorActionPlan,
        result: ExecutionResult,
        observation: dict[str, Any],
        classification: dict[str, Any],
    ) -> None:
        connector_id = str(observation.get("connector_id") or result.entity_id or "")
        try:
            from app.services.outcome_learning_service import get_outcome_learning_service

            await get_outcome_learning_service(self.settings).record_connector_action_outcome(
                org_id,
                connector_id or org_id,
                plan.invoke_action,
                "connector_action_executed" if result.success else "connector_action_failed",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("connector outcome record skipped: %s", exc)
        try:
            from app.services.intelligence_outcome_coordinator import get_intelligence_outcome_coordinator

            get_intelligence_outcome_coordinator(self.settings).record_response_async(
                org_id,
                agent_id=None,
                message_id=None,
                action_taken={
                    "type": "chat_connector_execute",
                    "action": plan.invoke_action,
                    "tool_name": plan.tool_name,
                    "connector_id": connector_id,
                },
                response={
                    "answer": result.body,
                    "success": result.success,
                    "url": result.result_url,
                    "strategy_key": "chat_connector_execute:v1",
                },
                classification={
                    **classification,
                    "intent": "workflow_execution",
                    "learning_layers": ["v1", "v7", "v8"],
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("intelligence outcome record skipped: %s", exc)


_chat_connector_execution_service: ChatConnectorExecutionService | None = None


def get_chat_connector_execution_service(
    settings: Settings | None = None,
) -> ChatConnectorExecutionService:
    global _chat_connector_execution_service
    if _chat_connector_execution_service is None or settings is not None:
        _chat_connector_execution_service = ChatConnectorExecutionService(settings)
    return _chat_connector_execution_service
