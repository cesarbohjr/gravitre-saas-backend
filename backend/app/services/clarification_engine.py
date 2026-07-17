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

    # Connector writes with an explicit vendor target — do not ask the generic
    # "which record/workflow" question (leaks intents like workflow_execution).
    SLACK_SEND_PATTERN = re.compile(
        r"(?:\b(?:post|send|notify|draft|compose)\b.+\bslack\b)"
        r"|(?:\bslack\b.+\b(?:post|send|message|notify|draft|compose)\b)",
        re.I,
    )
    EMAIL_SEND_PATTERN = re.compile(
        r"(?:\b(?:send|compose|draft|email)\b.+\b(?:email|outlook|microsoft\s*365|o365|gmail)\b)"
        r"|(?:\b(?:outlook|microsoft\s*365|o365|gmail)\b.+\b(?:send|compose|draft|email)\b)"
        r"|(?:\bsend\s+(?:an?\s+)?email\b)",
        re.I,
    )
    AUTONOMY_HINT = re.compile(
        r"\b(you decide|any record|pick one|choose for me|use any|surprise me|just pick)\b",
        re.I,
    )
    SLACK_CHANNEL_TOKEN = re.compile(
        r"(#[\w-]+)"
        r"|(?:\bin|to)\s+(?:the\s+)?([a-z0-9_-]+)\s+channel\b"
        r"|(?:\bchannel\s+)([a-z0-9_-]+)\b"
        r"|(?:\b(?:to|in)\s+slack\b)",
        re.I,
    )
    QUOTED = re.compile(r"[\"']([^\"']{1,500})[\"']")
    PLACEHOLDER_MESSAGE = re.compile(
        r"^(?:a\s+)?(?:message|msg|note|notification|update|summary|this|it)$",
        re.I,
    )

    INTENT_ACTION_LABELS: dict[str, str] = {
        "workflow_execution": "do that",
        "optimization": "optimize this",
        "data_analysis": "analyze this",
        "connector_action": "run that connector action",
        "search": "search",
        "question": "answer that",
    }

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
        pending: dict[str, Any] = {}
        if conversation_id and org_id:
            state = await self._state.get_task_state(conversation_id, org_id)
            clarified = state.get("clarified_params") or {}
            pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}

        # Multi-turn Slack: channel already staged — treat this turn as the message body.
        if self._is_slack_awaiting_body(pending, clarified):
            return {
                "should_clarify": False,
                "trigger_type": None,
                "question": None,
                "reason": "Resuming Slack send with previously clarified channel.",
            }

        rule_result = self._rule_based_trigger(
            classification,
            context,
            understanding or {},
            clarified,
            confidence,
            pending=pending,
        )
        if rule_result:
            question = await self.generate_clarification_question(
                rule_result["trigger_type"],
                classification,
                context,
                conversation_history or [],
                rule_result.get("template_vars") or {},
            )
            if conversation_id and org_id and rule_result.get("persist_updates"):
                try:
                    await self._state.update_task_state(
                        conversation_id,
                        org_id,
                        rule_result["persist_updates"],
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("clarification persist failed: %s", exc)
            return {
                "should_clarify": True,
                "trigger_type": rule_result["trigger_type"],
                "question": question,
                "reason": rule_result["reason"],
                "template_vars": rule_result.get("template_vars") or {},
            }

        if confidence < self.ESCALATION_THRESHOLD and classification.get("requires_action"):
            question = await self.generate_clarification_question(
                "under_specified_action",
                classification,
                context,
                conversation_history or [],
                {
                    "action": self._humanize_action(classification.get("intent") or "this action"),
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

    @staticmethod
    def _is_slack_awaiting_body(pending: dict[str, Any], clarified: dict[str, Any]) -> bool:
        if str(pending.get("status") or "") != "awaiting_params":
            return False
        params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
        if str(params.get("integration") or "").lower() == "slack":
            return bool(params.get("channel") or clarified.get("slack_channel"))
        return str(clarified.get("intent") or "") == "slack_send" and bool(
            clarified.get("slack_channel")
        )

    def _rule_based_trigger(
        self,
        classification: dict[str, Any],
        context: dict[str, Any],
        understanding: dict[str, Any],
        clarified: dict[str, Any],
        confidence: float,
        *,
        pending: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        request = str(classification.get("request") or "")
        lowered = request.lower()
        pending = pending or {}

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
                        "action_description": self._humanize_action(
                            classification.get("intent") or "perform this action"
                        ),
                    },
                }

        connectors_needed = understanding.get("connector_dependencies") or []
        connected = {
            str(c).lower()
            for c in (context.get("connected_integrations") or context.get("connectedIntegrations") or [])
        }
        # STA-307 — multi-connector asks belong to orchestration (correct labels +
        # zero-runnable blocked), not a single-connector unavailable clarify.
        if len(connectors_needed) < 2:
            for connector in connectors_needed:
                if connector.lower() not in connected and clarified.get(f"connector_{connector}") != "connected":
                    return {
                        "trigger_type": "connector_unavailable",
                        "reason": f"Required connector {connector} is not connected.",
                        "template_vars": {"connector": connector.replace("_", " ").title()},
                    }

        # Slack send/post: ask for message body (and channel if missing) — never
        # surface raw intents like "workflow_execution".
        if classification.get("requires_action") and self.SLACK_SEND_PATTERN.search(request):
            slack_trigger = self._slack_send_clarification(request, clarified)
            if slack_trigger is not None:
                return slack_trigger
            # Channel + body present (or already clarified) — let mapper/execution proceed.
            return None

        # Follow-up body for a staged Slack send should not hit generic "missing target".
        if self._is_slack_awaiting_body(pending, clarified):
            return None

        if classification.get("requires_action") and self.ACTION_VERBS.search(request):
            if not clarified.get("action_target") and not understanding.get("entities"):
                # Email / Outlook: ask for concrete fields, not a vague "which record".
                if self.EMAIL_SEND_PATTERN.search(request):
                    return {
                        "trigger_type": "missing_required_param",
                        "reason": "Email send missing recipient/subject/body.",
                        "template_vars": {
                            "action": "send that email",
                            "missing_param": (
                                "the recipient email, subject, and body "
                                "(or say “use my last HubSpot contact” / paste an address)"
                            ),
                        },
                    }
                # User explicitly deferred choice — do not block with a blank target ask.
                if self.AUTONOMY_HINT.search(request):
                    return None
                return {
                    "trigger_type": "missing_required_param",
                    "reason": "Action request missing target.",
                    "template_vars": {
                        "action": self._humanize_action(classification.get("intent") or "complete this"),
                        "missing_param": (
                            "a specific target — reply with a name, ID, or link, "
                            "or ask me to search HubSpot/contacts first and pick from results"
                        ),
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
                    "action": self._humanize_action(classification.get("intent") or "help with this"),
                    "specific_question": "What is the target and desired outcome?",
                },
            }

        return None

    def _humanize_action(self, value: str) -> str:
        """Never show snake_case classifier intents in user-facing copy."""
        raw = str(value or "").strip()
        if not raw:
            return "complete this"
        key = raw.lower().replace(" ", "_")
        if key in self.INTENT_ACTION_LABELS:
            return self.INTENT_ACTION_LABELS[key]
        if "_" in raw:
            return raw.replace("_", " ")
        return raw

    def _slack_channel_label(self, request: str) -> str | None:
        match = self.SLACK_CHANNEL_TOKEN.search(request)
        if not match:
            return None
        if match.group(1):
            return match.group(1).lstrip("#")
        if match.group(2):
            return match.group(2)
        if match.group(3):
            return match.group(3)
        # "(?:to|in) slack" with no named channel — default like the mapper.
        return "general"

    def _slack_message_body(self, request: str) -> str | None:
        from app.services.chat_message_normalize import strip_assistant_scope_prefix

        request = strip_assistant_scope_prefix(request)
        quoted = self.QUOTED.findall(request)
        if quoted:
            return quoted[-1].strip()
        post_match = re.search(
            r"(?:post|send|notify|message|draft|compose)\s+(?:a\s+|this\s+)?(.+?)"
            r"(?:\s+(?:to|in)\s+(?:the\s+)?(?:slack|#|[\w-]+\s+channel)|"
            r"\s+for\s+approval|$)",
            request,
            re.I,
        )
        if not post_match:
            return None
        body = post_match.group(1).strip(" .")
        # Drop trailing "… channel" fragments when channel was captured in the body group.
        body = re.sub(r"\s+(?:in|to)\s+slack\b.*$", "", body, flags=re.I).strip()
        if not body or self.PLACEHOLDER_MESSAGE.match(body):
            return None
        if body.lower() in {"message in slack", "a message in slack"}:
            return None
        return body

    def _slack_send_clarification(
        self,
        request: str,
        clarified: dict[str, Any],
    ) -> dict[str, Any] | None:
        if clarified.get("slack_message") or clarified.get("action_target"):
            return None
        channel = self._slack_channel_label(request) or clarified.get("slack_channel")
        if isinstance(channel, str):
            channel = channel.lstrip("#").strip() or None
        else:
            channel = None
        body = self._slack_message_body(request)
        if body and channel:
            return None
        if not body:
            where = f"#{channel}" if channel else "Slack"
            result: dict[str, Any] = {
                "trigger_type": "missing_required_param",
                "reason": "Slack send missing message body.",
                "template_vars": {
                    "action": f"send a Slack message to {where}" if channel else "send a Slack message",
                    "missing_param": "what the message should say",
                },
            }
            # Persist channel so the next turn ("sure, say hi…") can resume.
            if channel:
                result["persist_updates"] = {
                    "clarified_params": {
                        "slack_channel": channel,
                        "intent": "slack_send",
                    },
                    "pending_task": {
                        "type": "connector_action",
                        "status": "awaiting_params",
                        "params": {
                            "tool_name": "slack_send_message",
                            "invoke_action": "slack.post_message",
                            "integration": "slack",
                            "kind": "write",
                            "label": "Send Slack message",
                            "channel": channel,
                            "args": {"channel": channel},
                        },
                    },
                    "recent_user_messages": [request],
                }
            return result
        # Body present but no channel cue.
        return {
            "trigger_type": "missing_required_param",
            "reason": "Slack send missing channel.",
            "template_vars": {
                "action": "send a Slack message",
                "missing_param": "which channel to post in (for example #general)",
            },
        }

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
