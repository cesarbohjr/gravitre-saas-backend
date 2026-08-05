"""F1 — Retrieve-before-generate hard gate.

Generation (classical ReAct, ChatActionMapper orch planning, LIVE orch staging)
is only permitted when retrieval genuinely found nothing. Pack-common or
installed-workflow hits stage a retrieved plan. Ambiguous pack-shaped
utterances clarify instead of fabricating steps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

RetrieveKind = Literal[
    "pack_common_list_create",
    "pack_common_msp_enrich",
    "installed_workflow",
    "clarify",
]


@dataclass(frozen=True)
class RetrievedPlan:
    kind: RetrieveKind
    user_message: str
    dialogue_mode: str  # confirm | clarifying
    source: str
    pending_type: str | None = None
    pending_status: str | None = None
    params: dict[str, Any] | None = None
    connector_plan: Any | None = None  # ConnectorActionPlan when list-create
    block_fabrication: bool = False


_AMBIGUOUS_MULTI_STEP = re.compile(
    r"\b(?:enrich|sync|then|and then)\b.+\b(?:list|contacts?|hubspot|apollo|clay)\b|"
    r"\b(?:list|contacts?)\b.+\b(?:enrich|sync)\b",
    re.I,
)


def retrieve_plan_or_none(
    message: str,
    *,
    org_id: str | None = None,
    connected_integrations: list[str] | tuple[str, ...] | None = None,
    client: Any = None,
    require_pack_install: bool = False,
) -> RetrievedPlan | None:
    """Hard gate: pack-common / installed workflow → stage; ambiguous → clarify.

    Returns None only when generation is allowed (genuine retrieve miss and
    not an ambiguous fabricate-risk utterance).
    """
    text = (message or "").strip()
    if not text:
        return None

    from app.services.pack_common_intent_defaults import (
        PACK_IDS,
        format_pack_common_msp_enrich_confirm_message,
        try_pack_common_list_create_plan,
        try_pack_common_msp_enrich_workflow_plan,
        _AMBIGUOUS_LIST_REF,
    )

    connected = list(connected_integrations or [])

    # 1) MSP Clay→HubSpot enrich (retrieved pack workflow constants)
    enrich = try_pack_common_msp_enrich_workflow_plan(
        text, connected_integrations=connected
    )
    if enrich is not None:
        if require_pack_install and client is not None and org_id:
            installed = _org_has_pack(client, org_id, PACK_IDS)
            if installed is False:
                return RetrievedPlan(
                    kind="clarify",
                    user_message=(
                        "That looks like an MSP / Prospecting pack workflow, but the "
                        "pack isn't installed for this workspace yet. Install the "
                        "MSP Intelligence Pack (or Prospecting Intelligence Pack) "
                        "from Marketplace, then ask again — or tell me to open install."
                    ),
                    dialogue_mode="clarifying",
                    source="retrieve_plan_gate_pack_not_installed",
                    block_fabrication=True,
                )
        return RetrievedPlan(
            kind="pack_common_msp_enrich",
            user_message=format_pack_common_msp_enrich_confirm_message(enrich),
            dialogue_mode="confirm",
            source="retrieve_plan_gate_msp_enrich",
            pending_type="create_workflow",
            pending_status="awaiting_confirm",
            params=dict(enrich),
            block_fabrication=True,
        )

    # 2) Pack-common list create
    list_plan = try_pack_common_list_create_plan(
        text, connected_integrations=connected
    )
    if list_plan is not None:
        if require_pack_install and client is not None and org_id:
            from app.services.pack_common_intent_defaults import _MSP_PACK_HINT

            if _MSP_PACK_HINT.search(text):
                installed = _org_has_pack(client, org_id, PACK_IDS)
                if installed is False:
                    return RetrievedPlan(
                        kind="clarify",
                        user_message=(
                            "That list create looks pack-scoped, but the MSP / "
                            "Prospecting pack isn't installed. Install it from "
                            "Marketplace, or rephrase as a plain HubSpot/Apollo "
                            "list create without pack defaults."
                        ),
                        dialogue_mode="clarifying",
                        source="retrieve_plan_gate_pack_not_installed_list",
                        block_fabrication=True,
                    )
        return RetrievedPlan(
            kind="pack_common_list_create",
            user_message="",  # caller formats write approval
            dialogue_mode="confirm",
            source="retrieve_plan_gate_list_create",
            pending_type="connector_action",
            pending_status="awaiting_confirm",
            connector_plan=list_plan,
            block_fabrication=True,
        )

    # 3) Installed org workflow name/slug match (retrieve, don't invent)
    if client is not None and org_id:
        wf = _match_installed_workflow(client, org_id, text)
        if wf is not None:
            return wf

    # 4) Ambiguous pack-shaped enrich/list phrasing — clarify, never fabricate.
    # Only fire on enrich/sync + vague list refs (TRY-chip invent class), not
    # every casual "the list" mention — and not concrete multi-connector
    # orchestrations (e.g. Google Sheet → HubSpot contact) that name real tools.
    pack_shaped_ambiguous = bool(_AMBIGUOUS_LIST_REF.search(text)) and bool(
        re.search(r"\b(?:enrich|clay|sync|apollo|hubspot|msp)\b", text, re.I)
    )
    pack_risk_signal = bool(
        re.search(r"\b(?:enrich|clay|apollo|msp|prospecting)\b", text, re.I)
    )
    multi_step_guess = (
        pack_risk_signal
        and bool(_AMBIGUOUS_MULTI_STEP.search(text))
        and len(text) >= 24
        and (not _has_concrete_tool_anchors(text))
    )
    if pack_shaped_ambiguous or multi_step_guess:
        return RetrievedPlan(
            kind="clarify",
            user_message=(
                "I don't want to invent steps here. Which connectors and lists "
                "should I use? For example: enrich Apollo list \"MSP Prospects\" "
                "with Clay into HubSpot list \"MSPs\", or name the exact workflow."
            ),
            dialogue_mode="clarifying",
            source="retrieve_plan_gate_ambiguous",
            block_fabrication=True,
        )

    return None


def _has_concrete_tool_anchors(text: str) -> bool:
    """True when the utterance already names vendors + objects enough to retrieve later."""
    lower = text.lower()
    vendors = sum(
        1
        for v in (
            "apollo",
            "hubspot",
            "clay",
            "slack",
            "gmail",
            "salesforce",
            "asana",
            "monday",
            "google",
            "drive",
            "sheet",
        )
        if v in lower
    )
    return vendors >= 2 and bool(
        re.search(
            r"\b(?:list|segment|deal|contact|issue|task|item|sheet|rows?|file|doc)\b",
            lower,
        )
    )


def _org_has_pack(
    client: Any, org_id: str, pack_ids: frozenset[str] | set[str]
) -> bool | None:
    """Return True/False when install state is known; None when lookup fails.

    Fail-open (None) on infrastructure errors so a flaky installs table does not
    silently block every pack-common retrieve. Fail-closed only when the query
    succeeds and the pack is absent.
    """
    try:
        from app.services.recommendation_heuristics_service import load_installed_packs

        installed = load_installed_packs(client, org_id) or set()
        if not isinstance(installed, (set, frozenset, list, tuple)):
            return None
        normalized = {str(x).strip().lower() for x in installed if str(x).strip()}
        wanted = {str(x).strip().lower() for x in pack_ids}
        return bool(normalized & wanted)
    except Exception:  # noqa: BLE001
        return None


def _match_installed_workflow(
    client: Any, org_id: str, message: str
) -> RetrievedPlan | None:
    """Match message against org workflows that are marketplace-installed."""
    try:
        from app.marketplace.adoption import find_active_installs_for_entity
        from app.workflows.repository import list_workflows
    except Exception:  # noqa: BLE001
        return None

    try:
        workflows = list_workflows(client, org_id) or []
    except Exception:  # noqa: BLE001
        return None

    text = message.lower()
    # Prefer explicit "run/start/trigger workflow X" phrasing
    if not re.search(r"\b(?:run|start|trigger|execute|launch)\b.+\bworkflow\b", text) and not re.search(
        r"\bworkflow\b.+\b(?:named|called)\b",
        text,
    ):
        return None

    for wf in workflows:
        if not isinstance(wf, dict):
            continue
        wf_id = str(wf.get("id") or "").strip()
        name = str(wf.get("name") or "").strip()
        slug = str(wf.get("slug") or wf.get("workflow_slug") or "").strip()
        if not wf_id or not name:
            continue
        name_l = name.lower()
        slug_l = slug.lower()
        if name_l not in text and (not slug_l or slug_l not in text):
            continue
        # Confirm install binding when possible
        try:
            installs = find_active_installs_for_entity(
                client, org_id=org_id, entity_type="workflow", entity_id=wf_id
            )
            if installs is not None and len(list(installs or [])) == 0:
                # Also accept non-marketplace org workflows when explicitly named
                pass
        except Exception:  # noqa: BLE001
            pass
        return RetrievedPlan(
            kind="installed_workflow",
            user_message=(
                f"I'll run your existing workflow **{name}** "
                f"(retrieved definition — not a new invented plan).\n\n"
                "Reply **yes** to start it, or tell me what to change."
            ),
            dialogue_mode="confirm",
            source="retrieve_plan_gate_installed_workflow",
            pending_type="create_workflow",
            pending_status="awaiting_confirm",
            params={
                "type": "execute_workflow",
                "status": "awaiting_confirm",
                "workflow_id": wf_id,
                "workflow_name": name,
                "workflow_slug": slug,
                "source": "retrieve_plan_gate_installed_workflow",
            },
            block_fabrication=True,
        )
    return None


async def stage_retrieved_plan_turn(
    retrieved: RetrievedPlan,
    *,
    org_id: str,
    conversation_id: str,
    message: str,
    task_state: dict[str, Any] | None,
    client: Any,
    settings: Any,
) -> dict[str, Any]:
    """Persist pending state for a retrieved plan and return a stop_pipeline turn."""
    from app.services.conversation_state_service import get_conversation_state_service
    from app.services.user_facing_copy_guard import finalize_user_facing_message

    state = get_conversation_state_service(settings)

    if retrieved.kind == "clarify":
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarify",
            "message": finalize_user_facing_message(
                retrieved.user_message, context="retrieve_plan_gate_clarify"
            ),
            "task_state": task_state,
            "answer_explanation": "Retrieve-before-generate (clarify, no fabrication)",
            "model": "retrieve_plan_gate",
            "unified_outcome_kind": "clarifying_question",
            "block_fabrication": True,
        }

    if retrieved.kind == "pack_common_list_create" and retrieved.connector_plan is not None:
        from app.services.chat_connector_execution_service import (
            ChatConnectorExecutionService,
        )
        from app.services.connector_action_workflows import (
            format_write_approval_message,
            missing_params_stage_patch,
        )

        plan = retrieved.connector_plan
        staged_missing = missing_params_stage_patch(
            plan, message or "", task_state=task_state or {}
        )
        if staged_missing:
            clarification, stage_patch = staged_missing
            await state.update_task_state(
                conversation_id,
                org_id,
                {
                    **stage_patch,
                    "recent_user_messages": [message or ""],
                },
                client=client,
            )
            refreshed = await state.get_task_state(
                conversation_id, org_id, client=client
            )
            return {
                "stop_pipeline": True,
                "dialogue_mode": clarification.dialogue_mode or "clarify",
                "message": finalize_user_facing_message(
                    clarification.message, context="retrieve_plan_gate_list_params"
                ),
                "task_state": refreshed,
                "pending_task": (refreshed or {}).get("pending_task"),
                "workflow_status": clarification.status,
                "answer_explanation": "Retrieve-before-generate (list create awaiting params)",
                "model": "retrieve_plan_gate",
                "unified_outcome_kind": "clarifying_question",
                "block_fabrication": True,
            }

        pending_params = {
            **ChatConnectorExecutionService.plan_to_dict(plan),
            "status": "awaiting_confirm",
            "source": retrieved.source,
        }
        await state.update_task_state(
            conversation_id,
            org_id,
            {
                "pending_task": {
                    "type": "connector_action",
                    "status": "awaiting_confirm",
                    "params": pending_params,
                },
                "recent_user_messages": [message or ""],
            },
            client=client,
        )
        refreshed = await state.get_task_state(conversation_id, org_id, client=client)
        return {
            "stop_pipeline": True,
            "dialogue_mode": "confirm",
            "message": finalize_user_facing_message(
                format_write_approval_message(plan),
                context="retrieve_plan_gate_list_confirm",
            ),
            "task_state": refreshed,
            "pending_task": (refreshed or {}).get("pending_task"),
            "workflow_status": "awaiting_confirm",
            "answer_explanation": "Retrieve-before-generate (pack-common list create)",
            "model": "retrieve_plan_gate",
            "unified_outcome_kind": "connector_tool_proposal",
            "block_fabrication": True,
        }

    # MSP enrich / installed workflow
    params = dict(retrieved.params or {})
    await state.update_task_state(
        conversation_id,
        org_id,
        {
            "clarified_params": params,
            "pending_task": {
                "type": retrieved.pending_type or "create_workflow",
                "status": retrieved.pending_status or "awaiting_confirm",
                "params": params,
            },
            "recent_user_messages": [message or ""],
        },
        client=client,
    )
    refreshed = await state.get_task_state(conversation_id, org_id, client=client)
    return {
        "stop_pipeline": True,
        "dialogue_mode": retrieved.dialogue_mode or "confirm",
        "message": finalize_user_facing_message(
            retrieved.user_message, context="retrieve_plan_gate_stage"
        ),
        "task_state": refreshed,
        "pending_task": (refreshed or {}).get("pending_task"),
        "workflow_status": "awaiting_confirm",
        "answer_explanation": f"Retrieve-before-generate ({retrieved.kind})",
        "model": "retrieve_plan_gate",
        "unified_outcome_kind": "confirmation_request",
        "block_fabrication": True,
    }
