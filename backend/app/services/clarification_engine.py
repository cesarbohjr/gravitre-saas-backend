"""Focused clarifying questions when intent or context is ambiguous."""
from __future__ import annotations

import asyncio
import re
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.conversation_state_service import get_conversation_state_service

logger = get_logger(__name__)


class ClarificationEngine:
    """
    Generates focused clarifying questions when TaskClassifier detects ambiguity.
    Rule-based detection first; LLM only for natural-language question polish.
    """

    CLARIFICATION_THRESHOLD = 0.65
    ESCALATION_THRESHOLD = 0.40

    CLARIFICATION_TRIGGERS = {
        "ambiguous_entity": {
            "condition": "entity could refer to multiple things",
            "question_template": "Which {entity_type} did you mean — {options}?",
        },
        "missing_required_param": {
            "condition": "required action parameter absent",
            "question_template": "To {action}, I need to know {missing_param}. Could you share that?",
        },
        "under_specified_action": {
            "condition": "action type clear but scope/target missing",
            "question_template": "I can help with {action}. {specific_question}",
        },
        "high_risk_confirmation": {
            "condition": "action is irreversible or customer-facing",
            "question_template": "This will {action_description}. Should I proceed?",
        },
        "connector_unavailable": {
            "condition": "required connector not connected for this org",
            "question_template": "To do this, I'd need access to {connector}. Would you like to connect it first?",
        },
    }

    ACTION_VERBS = re.compile(
        r"\b(delete|remove|cancel|send|publish|deploy|execute|run|update|archive)\b",
        re.I,
    )

    AGENT_CREATE_PATTERN = re.compile(
        r"\b(create|build|make|set up|spin up|provision|add|generate|draft)\b.*\bagent\b",
        re.I,
    )

    WORKFLOW_CREATE_PATTERN = re.compile(
        r"\b(create|build|make|set up|spin up|provision|add|generate|draft)\b.*\b(workflow|automation|playbook)\b",
        re.I,
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._state = get_conversation_state_service(self.settings)

    async def should_clarify(
        self,
        classification: dict[str, Any],
        context: dict[str, Any],
        conversation_history: list[dict] | None,
        *,
        conversation_id: str | None = None,
        org_id: str | None = None,
        understanding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        confidence = float(
            classification.get("classification_confidence")
            or classification.get("confidence")
            or 0.55
        )
        request = str(classification.get("request") or "")
        clarified: dict[str, Any] = {}
        if conversation_id and org_id:
            state = await self.load_clarification_state(conversation_id, org_id)
            clarified = state.get("clarified_params") or {}

        rule_result = self._rule_based_trigger(
            classification,
            context,
            understanding or {},
            clarified,
            confidence,
        )
        if rule_result:
            question = await self.generate_clarification_question(
                rule_result["trigger_type"],
                classification,
                context,
                conversation_history or [],
                rule_result.get("template_vars") or {},
            )
            return {
                "should_clarify": True,
                "trigger_type": rule_result["trigger_type"],
                "question": question,
                "reason": rule_result["reason"],
            }

        if confidence < self.ESCALATION_THRESHOLD and classification.get("requires_action"):
            question = await self.generate_clarification_question(
                "under_specified_action",
                classification,
                context,
                conversation_history or [],
                {
                    "action": classification.get("intent") or "this action",
                    "specific_question": "Could you share the target and any constraints?",
                },
            )
            return {
                "should_clarify": True,
                "trigger_type": "under_specified_action",
                "question": question,
                "reason": f"Confidence {confidence:.0%} is too low to proceed without clarification.",
            }

        return {
            "should_clarify": False,
            "trigger_type": None,
            "question": None,
            "reason": "Sufficient context and confidence.",
        }

    def _rule_based_trigger(
        self,
        classification: dict[str, Any],
        context: dict[str, Any],
        understanding: dict[str, Any],
        clarified: dict[str, Any],
        confidence: float,
    ) -> dict[str, Any] | None:
        request = str(classification.get("request") or "")
        lowered = request.lower()

        if understanding.get("conversational_create") or self.AGENT_CREATE_PATTERN.search(request):
            if not clarified.get("agent_name") and not clarified.get("agent_purpose"):
                return {
                    "trigger_type": "under_specified_action",
                    "reason": "Agent creation needs a name and purpose before proceeding.",
                    "template_vars": {
                        "action": "create your agent",
                        "specific_question": (
                            "What should we call it, and what should it help with "
                            "(for example sales outreach, support triage, or marketing research)?"
                        ),
                    },
                }

        if understanding.get("conversational_create") and self.WORKFLOW_CREATE_PATTERN.search(request):
            if not clarified.get("workflow_goal"):
                return {
                    "trigger_type": "under_specified_action",
                    "reason": "Workflow creation needs a goal and trigger before proceeding.",
                    "template_vars": {
                        "action": "build your workflow",
                        "specific_question": (
                            "What should trigger it, and what outcome do you want "
                            "(for example sync HubSpot deals daily or notify Slack on failures)?"
                        ),
                    },
                }

        if classification.get("requires_action") and classification.get("risk_level") in {
            "high",
            "critical",
        }:
            if clarified.get("high_risk_confirmed") != "yes":
                return {
                    "trigger_type": "high_risk_confirmation",
                    "reason": "High-risk action requires explicit confirmation.",
                    "template_vars": {
                        "action_description": f"{classification.get('intent') or 'perform this action'}",
                    },
                }

        connectors_needed = understanding.get("connector_dependencies") or []
        connected = {
            str(c).lower()
            for c in (context.get("connected_integrations") or context.get("connectedIntegrations") or [])
        }
        for connector in connectors_needed:
            if connector.lower() not in connected and clarified.get(f"connector_{connector}") != "connected":
                return {
                    "trigger_type": "connector_unavailable",
                    "reason": f"Required connector {connector} is not connected.",
                    "template_vars": {"connector": connector.replace("_", " ").title()},
                }

        if classification.get("requires_action") and self.ACTION_VERBS.search(request):
            if not clarified.get("action_target") and not understanding.get("entities"):
                return {
                    "trigger_type": "missing_required_param",
                    "reason": "Action request missing target.",
                    "template_vars": {
                        "action": classification.get("intent") or "complete this",
                        "missing_param": "which record, workflow, or resource to act on",
                    },
                }

        if confidence < self.CLARIFICATION_THRESHOLD and any(
            token in lowered for token in ("it", "this", "that", "them")
        ):
            if not clarified.get("resolved_entity"):
                return {
                    "trigger_type": "ambiguous_entity",
                    "reason": "Pronoun reference with low confidence.",
                    "template_vars": {
                        "entity_type": "item",
                        "options": "the specific workflow, agent, or connector you mean",
                    },
                }

        if (
            confidence < self.CLARIFICATION_THRESHOLD
            and classification.get("requires_action")
            and len(request.split()) < 6
        ):
            return {
                "trigger_type": "under_specified_action",
                "reason": "Under-specified action request.",
                "template_vars": {
                    "action": classification.get("intent") or "help with this",
                    "specific_question": "What is the target and desired outcome?",
                },
            }

        return None

    async def generate_clarification_question(
        self,
        trigger_type: str,
        classification: dict[str, Any],
        context: dict[str, Any],
        conversation_history: list[dict],
        template_vars: dict[str, Any] | None = None,
    ) -> str:
        _ = classification, context, conversation_history
        config = self.CLARIFICATION_TRIGGERS.get(trigger_type, {})
        template = str(config.get("question_template") or "Could you clarify what you need?")
        vars_ = template_vars or {}
        try:
            question = template.format(**vars_)
        except KeyError:
            question = template

        if len(question) > 20 and trigger_type != "high_risk_confirmation":
            polished = await self._polish_question(question)
            return polished or question
        return question

    async def _polish_question(self, draft: str) -> str | None:
        try:
            from app.services.model_router import TaskType, get_model_router

            response = await get_model_router(self.settings).complete(
                task_type=TaskType.CLASSIFICATION,
                prompt=(
                    "Rewrite as one natural clarifying question. No bullet lists.\n\n"
                    f"Draft: {draft}"
                ),
                system_prompt="Output a single concise question only.",
                org_id=None,
                temperature=0.0,
                max_tokens=120,
            )
            text = (response.content or "").strip()
            return text if text else None
        except Exception as exc:  # noqa: BLE001
            logger.debug("clarification polish skipped: %s", exc)
            return None

    async def load_clarification_state(self, conversation_id: str, org_id: str) -> dict[str, Any]:
        state = await self._state.get_task_state(conversation_id, org_id)
        return {"clarified_params": state.get("clarified_params") or {}}

    async def save_clarification_resolution(
        self,
        conversation_id: str,
        org_id: str,
        parameter: str,
        resolved_value: str,
    ) -> None:
        asyncio.create_task(
            self._state.remember_clarification(conversation_id, org_id, parameter, resolved_value)
        )


_clarification_engine: ClarificationEngine | None = None


def get_clarification_engine(settings: Settings | None = None) -> ClarificationEngine:
    global _clarification_engine
    if _clarification_engine is None or settings is not None:
        _clarification_engine = ClarificationEngine(settings)
    return _clarification_engine
