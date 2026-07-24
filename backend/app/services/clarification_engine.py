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
        task_state: dict[str, Any] = {}
        if conversation_id and org_id:
            task_state = await self._state.get_task_state(conversation_id, org_id)
            clarified = task_state.get("clarified_params") or {}
            pending = (
                task_state.get("pending_task")
                if isinstance(task_state.get("pending_task"), dict)
                else {}
            )

        # Multi-turn: params already staged on the shared ledger — resume, don't re-ask.
        from app.services.parameter_ledger import is_awaiting_params

        if is_awaiting_params(task_state or {"pending_task": pending}):
            return {
                "should_clarify": False,
                "trigger_type": None,
                "question": None,
                "reason": "Resuming connector action with previously staged parameters.",
            }

        rule_result = self._rule_based_trigger(
            classification,
            context,
            understanding or {},
            clarified,
            confidence,
            pending=pending,
            task_state=task_state,
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

    def _rule_based_trigger(
        self,
        classification: dict[str, Any],
        context: dict[str, Any],
        understanding: dict[str, Any],
        clarified: dict[str, Any],
        confidence: float,
        *,
        pending: dict[str, Any] | None = None,
        task_state: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        request = str(classification.get("request") or "")
        lowered = request.lower()
        pending = pending or {}
        task_state = task_state or {}

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
        # Advisory plan-first: never short-circuit on connector_unavailable — stage a
        # plan that lists missing connectors as blockers instead of blocking turn 1.
        from app.services.conversational_planning_engine import is_advisory_plan_first

        advisory_plan = is_advisory_plan_first(request)
        # STA-307 — multi-connector asks belong to orchestration (correct labels +
        # zero-runnable blocked), not a single-connector unavailable clarify.
        if not advisory_plan and len(connectors_needed) < 2:
            for connector in connectors_needed:
                if connector.lower() not in connected and clarified.get(f"connector_{connector}") != "connected":
                    return {
                        "trigger_type": "connector_unavailable",
                        "reason": f"Required connector {connector} is not connected.",
                        "template_vars": {"connector": connector.replace("_", " ").title()},
                    }

        # Follow-up for a staged connector action should not hit generic "missing target".
        from app.services.parameter_ledger import is_awaiting_params

        if is_awaiting_params(task_state or {"pending_task": pending}):
            return None

        # Advisory plan-first must present current_plan, not dive into catalog write
        # staging (e.g. Slack channel ask) that hijacks the turn before the plan
        # is shown — Round-2 test 4 false-PASS: plan in task_state but user saw
        # "need channel" / turn2 became connector-unavailable.
        if advisory_plan:
            return None

        # Generic catalog write clarification — live ledger read every turn.
        # Replaces Slack/Gmail-specific staging helpers (deleted).
        if classification.get("requires_action") and (
            self.SLACK_SEND_PATTERN.search(request)
            or self.EMAIL_SEND_PATTERN.search(request)
            or self.ACTION_VERBS.search(request)
        ):
            catalog_trigger = self._catalog_write_clarification(
                request,
                clarified,
                task_state=task_state,
            )
            if catalog_trigger is not None:
                return catalog_trigger
            if self.SLACK_SEND_PATTERN.search(request) or self.EMAIL_SEND_PATTERN.search(request):
                # Fields satisfied via ledger — proceed to mapper/execution.
                return None

        if classification.get("requires_action") and self.ACTION_VERBS.search(request):
            if not clarified.get("action_target") and not understanding.get("entities"):
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

        # Word-boundary only — substring "it" in "waitlist" / "this" in free text
        # used to fire a generic "Which item…" and drop named-vendor intents
        # (Twilio/SendGrid/Gmail) onto the wrong clarify path (Phase 1 breadth).
        pronoun_hit = bool(re.search(r"\b(it|this|that|them)\b", lowered))
        if confidence < self.CLARIFICATION_THRESHOLD and pronoun_hit:
            if not clarified.get("resolved_entity"):
                # Phase 5 — user corrections ("actually / I meant / use X instead")
                # are not platform-item asks.
                from app.services.gravitree_voice import detect_correction_phrase

                if detect_correction_phrase(request):
                    return None
                # Phase 4 — conversation-memory / account-recall questions often
                # contain "this conversation" / "that account" without a tool target.
                if re.search(
                    r"\b("
                    r"primary account|account name|from (the )?(start|beginning)|"
                    r"earlier in (this )?conversation|going forward|remember|"
                    r"codename|pipeline codename"
                    r")\b",
                    lowered,
                ):
                    return None
                # Post-action / ops inventory: "this organization" + connector status
                # is not a platform-item pronoun ask (was trapping clean read probes).
                if (
                    re.search(r"\b(this|that)\s+(org|organization)\b", lowered)
                    or re.search(
                        r"\b(what|which|list|show|give)\b.{0,48}\bconnectors?\b",
                        lowered,
                    )
                    or re.search(
                        r"\bconnectors?\b.{0,48}\b(connected|healthy|health|status|executable)\b",
                        lowered,
                    )
                ):
                    return None
                # Named vendor in the utterance → connector gate, not platform-item ask.
                named = self._named_connectors_in_text(request)
                if named:
                    for connector in named:
                        if connector.lower() not in connected and clarified.get(
                            f"connector_{connector}"
                        ) != "connected":
                            return {
                                "trigger_type": "connector_unavailable",
                                "reason": f"Required connector {connector} is not connected.",
                                "template_vars": {
                                    "connector": connector.replace("_", " ").title()
                                },
                            }
                    # Vendor named and connected — let mapper/ReAct proceed.
                    return None
                # Explicit email/slack write phrasing must not become "which workflow".
                if self.EMAIL_SEND_PATTERN.search(request) or self.SLACK_SEND_PATTERN.search(
                    request
                ):
                    return None
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
            # Run-history / recent-runs asks need workflow_runs (or honesty refusal),
            # not an under-specified-action clarify trap.
            try:
                from app.services.factual_claim_honesty import is_run_history_question

                if is_run_history_question(request):
                    return None
            except Exception:  # noqa: BLE001
                pass
            return {
                "trigger_type": "under_specified_action",
                "reason": "Under-specified action request.",
                "template_vars": {
                    "action": self._humanize_action(classification.get("intent") or "help with this"),
                    "specific_question": "What is the target and desired outcome?",
                },
            }

        return None

    # Aliases too generic to treat as an explicit vendor mention.
    _GENERIC_VENDOR_ALIASES = frozenset(
        {
            "email",
            "crm",
            "design",
            "analytics",
            "wiki",
            "spreadsheet",
            "sheet",
            "drive",
            "calendar",
            "teams",
            "support ticket",
            "support tickets",
            "pull request",
            "pull requests",
        }
    )

    def _named_connectors_in_text(self, text: str) -> list[str]:
        """Return catalog connector ids explicitly named in the user utterance."""
        from app.services.chat_connector_models import INTEGRATION_ALIASES

        found: list[str] = []
        lowered = (text or "").lower()
        for connector_id, aliases in INTEGRATION_ALIASES.items():
            # Always accept the canonical id as a word.
            needles = (connector_id.replace("_", " "), connector_id) + tuple(aliases)
            for alias in needles:
                a = str(alias or "").strip().lower()
                if not a or a in self._GENERIC_VENDOR_ALIASES:
                    continue
                if re.search(rf"\b{re.escape(a)}\b", lowered):
                    found.append(connector_id)
                    break
        return found

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

    def _catalog_write_clarification(
        self,
        request: str,
        clarified: dict[str, Any],
        *,
        task_state: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Generic ledger-backed clarify/stage for catalog write actions.

        Always reads the live ``parameter_ledger`` from task_state (Fix 1).
        Slack/Gmail-specific helpers were deleted — this is the only path.
        """
        from app.services.chat_connector_models import ConnectorActionPlan
        from app.services.parameter_ledger import (
            bind_args_from_ledger,
            get_ledger,
            ingest_message_slots,
            missing_required_fields,
            slot_confidence,
            stage_awaiting_params,
        )

        if clarified.get("slack_message") or clarified.get("action_target"):
            return None

        plan_hint = self._infer_catalog_write_plan(request)
        if plan_hint is None:
            return None

        # LIVE ledger — never reconstruct from clarified_params alone.
        live_state = dict(task_state or {})
        if "clarified_params" not in live_state and clarified:
            live_state["clarified_params"] = clarified
        ledger = ingest_message_slots(request, ledger=get_ledger(live_state))

        # Slack channel cue when present in this turn.
        if plan_hint.invoke_action == "slack.post_message":
            channel = ledger.get("channel") or self._slack_channel_label(request)
            if isinstance(channel, str) and channel.strip():
                ledger.upsert("channel", channel.lstrip("#").strip(), source="clarification")
            body = self._slack_message_body(request)
            if body:
                ledger.upsert("message", body, source="clarification")
                ledger.upsert("text", body, source="clarification")

        # Confidence-aware: promote likely first-name → email matches to medium slots.
        self._promote_likely_entity_matches(request, ledger, live_state)

        args = bind_args_from_ledger(plan_hint.invoke_action, dict(plan_hint.args or {}), ledger)
        # High confidence / safe defaults: use silently and note the assumption.
        if plan_hint.invoke_action == "gmail.messages.send" and args.get("to") and not args.get(
            "subject"
        ):
            # Only auto-default when recipient is high-confidence (not a guess).
            if slot_confidence(ledger, "to") == "high":
                args["subject"] = "Follow-up"
                ledger.upsert("subject", "Follow-up", source="default", confidence="high")

        missing = missing_required_fields(plan_hint.invoke_action, args, ledger)
        # Email: subject defaultable — drop from ask if high-confidence recipient present.
        if plan_hint.invoke_action == "gmail.messages.send" and args.get("to"):
            if slot_confidence(ledger, "to") == "high":
                missing = [m for m in missing if m.lower() not in {"subject"}]

        # Medium-confidence bound values still need propose/confirm (not silent use).
        propose_parts: list[str] = []
        for key, value in list(args.items()):
            if not isinstance(value, str) or not value.strip():
                continue
            if slot_confidence(ledger, key) != "medium":
                continue
            label = "recipient" if key in {"to", "email"} else key.replace("_", " ")
            propose_parts.append(f"{label} {value}")

        plan = ConnectorActionPlan(
            tool_name=plan_hint.tool_name,
            invoke_action=plan_hint.invoke_action,
            integration=plan_hint.integration,
            kind="write",
            label=plan_hint.label,
            args=args,
        )

        if propose_parts and not missing:
            proposal = "; ".join(propose_parts)
            return {
                "trigger_type": "missing_required_param",
                "reason": f"Proposing ledger match for confirmation: {proposal}",
                "template_vars": {
                    "action": plan_hint.label.lower(),
                    "missing_param": (
                        f"{proposal} — correct? Reply yes to proceed or send the right value"
                    ),
                },
                "persist_updates": {
                    **stage_awaiting_params(plan, ledger=ledger),
                    "recent_user_messages": [request],
                },
                "clarification_mode": "propose_confirm",
            }

        if propose_parts and missing:
            proposal = "; ".join(propose_parts)
            ask = ", ".join(missing)
            return {
                "trigger_type": "missing_required_param",
                "reason": f"Partial ledger match; still need {ask}.",
                "template_vars": {
                    "action": plan_hint.label.lower(),
                    "missing_param": f"{ask} (also confirm {proposal})",
                },
                "persist_updates": {
                    **stage_awaiting_params(plan, tuple(missing), ledger=ledger),
                    "recent_user_messages": [request],
                },
                "clarification_mode": "propose_confirm",
            }

        if not missing:
            return None

        # Low / no match → ask cleanly. When ledger already has high-confidence
        # fields, surface them so we never look like we forgot (Fix 1 / test 2).
        ask = ", ".join(missing)
        known_bits: list[str] = []
        for key in ("to", "email", "channel", "subject"):
            val = ledger.get(key)
            if val and slot_confidence(ledger, key) == "high":
                known_bits.append(f"{key}={val}")
        if known_bits:
            ask = f"{ask} (I already have {', '.join(known_bits)})"
        return {
            "trigger_type": "missing_required_param",
            "reason": f"{plan_hint.label} missing {ask} (live ledger consulted).",
            "template_vars": {
                "action": plan_hint.label.lower(),
                "missing_param": ask,
            },
            "persist_updates": {
                **stage_awaiting_params(plan, tuple(missing), ledger=ledger),
                "recent_user_messages": [request],
            },
        }

    def _promote_likely_entity_matches(
        self,
        request: str,
        ledger: Any,
        task_state: dict[str, Any],
    ) -> None:
        """Medium-confidence name→email from recent conversation context.

        Root-cause guard (Round-2 corruption): never embed EMAIL_RE after a
        greedy ``[^@]+`` gap — that backtracks into local-part suffixes
        (``moduleb@acme.test`` inside ``sarah.chen.moduleb@acme.test``).
        Always extract complete emails first, then score name→local-part tokens.
        """
        from app.services.parameter_ledger import extract_complete_emails

        if ledger.get("to"):
            return
        name_match = re.search(
            r"\b(?:to|for|email|ping|message)\s+([A-Z][a-z]{1,30})\b",
            request,
        )
        if not name_match:
            return
        first = name_match.group(1)
        if first.lower() in {"slack", "gmail", "email", "outlook", "the", "a", "an"}:
            return
        recent = list(task_state.get("recent_user_messages") or [])
        corpus = "\n".join(str(m) for m in recent[-12:])
        emails = extract_complete_emails(corpus)
        if not emails:
            return
        first_l = first.lower()
        name_hits: list[str] = []
        for email in emails:
            # Product-safety: proposed value must appear verbatim in context.
            if email not in corpus:
                continue
            local = email.split("@", 1)[0].lower()
            tokens = [tok for tok in re.split(r"[._+-]+", local) if tok]
            if first_l in tokens or (len(emails) == 1 and first_l in corpus.lower()):
                name_hits.append(email)
        unique = list(dict.fromkeys(name_hits))
        if len(unique) != 1:
            return
        chosen = unique[0]
        ledger.upsert(
            "to",
            chosen,
            source="likely_entity_match",
            confidence="medium",
        )
        ledger.upsert(
            "email",
            chosen,
            source="likely_entity_match",
            confidence="medium",
        )

    def _infer_catalog_write_plan(self, request: str) -> Any | None:
        """Map NL write intent to a catalog action for generic clarify/stage."""
        from app.services.chat_connector_models import ConnectorActionPlan

        if self.EMAIL_SEND_PATTERN.search(request):
            return ConnectorActionPlan(
                tool_name="gmail_messages_send",
                invoke_action="gmail.messages.send",
                integration="gmail",
                kind="write",
                label="Send Gmail message",
                args={},
            )
        if self.SLACK_SEND_PATTERN.search(request):
            return ConnectorActionPlan(
                tool_name="slack_send_message",
                invoke_action="slack.post_message",
                integration="slack",
                kind="write",
                label="Send Slack message",
                args={},
            )
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
