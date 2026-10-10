"""Structured multi-turn task state within a conversation thread."""
from __future__ import annotations

import threading
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.io_pool import run_io
from app.core.logging import get_logger
from app.services.conversation_write_guard import (
    ConversationWriteBlockedError,
    assert_conversation_create_allowed,
)
from app.workflows.repository import get_supabase_client
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

# Set while this service reads task_state to merge into and write back, so that
# read stays on the event loop with the write (see get_task_state).
_read_on_loop: ContextVar[bool] = ContextVar("task_state_read_on_loop", default=False)

# Striped locks: task_state read-merge-write for one conversation never
# interleaves with another in this process (writers run on the I/O pool).
_TASK_STATE_LOCKS = [threading.Lock() for _ in range(64)]


def _task_state_lock(conversation_id: str, org_id: str) -> threading.Lock:
    return _TASK_STATE_LOCKS[hash((conversation_id, org_id)) % len(_TASK_STATE_LOCKS)]

DEFAULT_TASK_STATE: dict[str, Any] = {
    "clarified_params": {},
    "rejected_options": [],
    "approved_actions": [],
    "current_plan": None,
    "completed_steps": [],
    "pending_steps": [],
    "persona_override": None,
    "preferred_tone": None,
    "unresolved_tasks": [],
    "suppressed_suggestions": [],
    "pending_task": None,
    "connector_session": {},
    "resolved_entities": {},
    # Recent user turns for multi-turn param fill (Slack channel → body, etc.).
    "recent_user_messages": [],
    # Recent connector invokes so honesty can refuse "I don't have that action"
    # after the same conversation already ran it (including validation_error).
    "recent_connector_invocations": [],
    # Module B — conversation-scoped parameter ledger (canonical slot store).
    "parameter_ledger": {"slots": {}, "pending_missing": []},
    # Module D — last expression-range variant index per category (phrase variety).
    "voice_expression_last": {},
    # Structured continuation for a READ offer. Not a write pending_task.
    "offered_action": None,
    # Phase A — structured reference resolution (not prose history).
    "previous_option_set": [],
    "previous_result": None,
    "active_analysis": None,
    "resolution_trace": None,
    # Audit §34.4 — read-only projection of the current business task.
    "compiled_task": None,
    # Phase C/E5 — typed execution plan + normalized observations.
    "execution_plan": None,
    "execution_observations": [],
    # 3.0-D — WRITE checkpoint must survive get_task_state normalize or the
    # next persist writes a stripped snapshot and crash-resume loses plan_id.
    "durable_checkpoint": None,
    "durable_session": None,
    # 3.0-D — finished-work reports must survive GET /state and persist merge.
    "durable_deliverable": None,
    "work_artifacts": [],
    "diagnostic_conclusion": None,
    "repair_budget": None,
    "repair_error_memory": [],
    # Phase E5 — governance continuation (confirmation/clarification/approval).
    "pending_action": None,
    # Phase D — unified turn trace (gateway → compose).
    "cognitive_turn_trace": None,
    # 2.0-H — grounded READ proof must survive get_task_state normalize.
    "provider_result_evidence": None,
    "proactive_operator": [],
    "business_entity": None,
    "last_read_preflight": None,
    "capability_id": None,
    "capability_route_reason": None,
    "cognitive_resolution_message": None,
    # The message resolved on the turn before, so a follow-up can tell whether
    # the answer it edits was the last thing said.
    "previous_resolution_message": None,
    "cognitive_resolution_needs": None,
    # Website-traffic answer under discussion (period, sources, open offer), so
    # "no, last month" or "which pages did best?" edit it instead of starting over.
    "analytics_frame": None,
    # READ-only Chromium visits must survive get_task_state normalize.
    "computer_browser_evidence": None,
    # Objective-first: the conversation's current business objective (contract,
    # constraints, plan digest, revision). Written by the cognitive kernel on
    # every surface (text, voice, agents) so "actually, make that Canadian MSPs"
    # revises the same objective instead of starting over.
    "active_objective": None,
}


class ConversationStateService:
    """Manages structured task state — distinct from message history and org memory."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self, client: Any | None = None) -> Any:
        return client or get_supabase_client(self.settings)

    @staticmethod
    def _normalize_state(raw: dict[str, Any] | None) -> dict[str, Any]:
        state = deepcopy(DEFAULT_TASK_STATE)
        if not raw:
            return state
        for key in DEFAULT_TASK_STATE:
            if key in raw and raw[key] is not None:
                state[key] = raw[key]
        clarified = raw.get("clarified_params")
        if isinstance(clarified, dict):
            state["clarified_params"] = {**state.get("clarified_params", {}), **clarified}
        return state

    async def get_task_state(
        self,
        conversation_id: str,
        org_id: str,
        *,
        client: Any | None = None,
        strict: bool = False,
    ) -> dict[str, Any]:
        """The conversation's task_state.

        A failed read returns the default state, unless ``strict``: then it
        raises, so a caller that must tell "no state" from "unknown state"
        (speculative adoption) can.
        """
        if not conversation_id or not org_id:
            return deepcopy(DEFAULT_TASK_STATE)
        from app.services.speculative_execution import current_scope

        scope = current_scope()
        if scope is not None:
            # A speculative run reads back what it would have written (its writes
            # are deferred until adoption), so it behaves like a confirmed run.
            overlay = scope.task_state_overlay.get((conversation_id, org_id))
            if overlay is not None:
                return deepcopy(overlay)
        try:
            query = (
                self._client(client)
                .table("conversations")
                .select("task_state")
                .eq("id", conversation_id)
                .eq("org_id", org_id)
                .limit(1)
            )
            if _read_on_loop.get():
                # Read-modify-write below: read and write with no await between,
                # exactly as before, so no other coroutine can write in between.
                rows = query.execute().data or []
            else:
                # A plain read: keep the blocking round trip off the event loop.
                rows = (await run_io(query.execute)).data or []
            if rows:
                return self._normalize_state(rows[0].get("task_state"))
        except Exception as exc:
            if strict:
                raise
            logger.debug(
                "get_task_state fallback conversation_id=%s error=%s",
                conversation_id,
                exc,
            )
        return deepcopy(DEFAULT_TASK_STATE)

    @staticmethod
    def _merge_task_state(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(current)
        for key, value in updates.items():
            if key == "clarified_params" and isinstance(value, dict):
                merged["clarified_params"] = {
                    **(merged.get("clarified_params") or {}),
                    **value,
                }
            elif key == "rejected_options" and isinstance(value, list):
                existing = list(merged.get("rejected_options") or [])
                merged["rejected_options"] = list(dict.fromkeys(existing + value))
            elif key == "suppressed_suggestions" and isinstance(value, list):
                existing = list(merged.get("suppressed_suggestions") or [])
                merged["suppressed_suggestions"] = list(dict.fromkeys(existing + value))
            elif key == "connector_session" and isinstance(value, dict):
                merged["connector_session"] = {
                    **(merged.get("connector_session") or {}),
                    **value,
                }
            elif key == "resolved_entities" and isinstance(value, dict):
                merged["resolved_entities"] = {
                    **(merged.get("resolved_entities") or {}),
                    **value,
                }
            elif key == "parameter_ledger" and isinstance(value, dict):
                # Deep-merge slots; pending_missing replaces when provided.
                current_ledger = (
                    merged.get("parameter_ledger")
                    if isinstance(merged.get("parameter_ledger"), dict)
                    else {}
                )
                current_slots = (
                    safe_normalize_stored_dict(current_ledger, key="slots")
                    if isinstance(current_ledger.get("slots"), dict)
                    else {}
                )
                incoming_slots = (
                    safe_normalize_stored_dict(value, key="slots")
                    if isinstance(value.get("slots"), dict)
                    else {}
                )
                merged["parameter_ledger"] = {
                    "slots": {**current_slots, **incoming_slots},
                    "pending_missing": list(
                        value["pending_missing"]
                        if "pending_missing" in value
                        else (current_ledger.get("pending_missing") or [])
                    ),
                }
            elif key == "recent_user_messages" and isinstance(value, list):
                existing = list(merged.get("recent_user_messages") or [])
                merged["recent_user_messages"] = (existing + list(value))[-12:]
            elif key == "recent_connector_invocations" and isinstance(value, list):
                existing = list(merged.get("recent_connector_invocations") or [])
                combined = [row for row in list(value) + existing if isinstance(row, dict)]
                deduped: list[dict[str, Any]] = []
                seen: set[str] = set()
                for row in combined:
                    vendor = str(row.get("vendor") or "").strip().lower()
                    action = str(row.get("action") or "").strip().lower()
                    marker = f"{vendor}:{action}"
                    if not vendor or marker in seen:
                        continue
                    seen.add(marker)
                    deduped.append(
                        {
                            "vendor": vendor,
                            "action": action,
                            "error_code": str(row.get("error_code") or "")[:80],
                        }
                    )
                    if len(deduped) >= 8:
                        break
                merged["recent_connector_invocations"] = deduped
            else:
                merged[key] = value
        return merged

    async def _persist_state(
        self,
        conversation_id: str,
        org_id: str,
        updates: dict[str, Any],
        *,
        client: Any | None = None,
    ) -> None:
        if not conversation_id or not org_id:
            return
        # The read-merge-write is synchronous I/O: it runs on the I/O pool, in
        # a copy of this context (speculative scope, turn token), so a slow
        # database never stalls the voice event loop. A per-conversation lock
        # keeps concurrent writers in this process from losing each other's
        # updates, as running it on the loop with no await used to.
        await run_io(self._persist_state_sync, conversation_id, org_id, updates, client)

    def _read_task_state_sync(self, conversation_id: str, org_id: str, client: Any | None) -> dict[str, Any]:
        from app.services.speculative_execution import current_scope

        scope = current_scope()
        if scope is not None:
            overlay = scope.task_state_overlay.get((conversation_id, org_id))
            if overlay is not None:
                return deepcopy(overlay)
        rows = (
            self._client(client)
            .table("conversations")
            .select("task_state")
            .eq("id", conversation_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return self._normalize_state(rows[0].get("task_state")) if rows else deepcopy(DEFAULT_TASK_STATE)

    def _persist_state_sync(
        self,
        conversation_id: str,
        org_id: str,
        updates: dict[str, Any],
        client: Any | None,
    ) -> None:
        original_updates = updates
        try:
            with _task_state_lock(conversation_id, org_id):
                try:
                    current = self._read_task_state_sync(conversation_id, org_id, client)
                except Exception as exc:  # noqa: BLE001 - same fallback get_task_state uses
                    logger.debug("get_task_state fallback conversation_id=%s error=%s", conversation_id, exc)
                    current = deepcopy(DEFAULT_TASK_STATE)
                from app.services.execution_plan_adapters import enrich_task_state_patch

                updates = enrich_task_state_patch(updates, current_state=current)
                merged = self._merge_task_state(current, updates)
                from app.services.speculative_execution import current_scope

                scope = current_scope()
                if scope is None:
                    from app.services.turn_cancellation import current_turn_cancelled

                    if current_turn_cancelled():
                        # Fence: the turn this write belongs to was cancelled
                        # (stopped, cut off, superseded). Its state must not
                        # overwrite what the user did next, even when a
                        # background replay lands late. Checked under the lock,
                        # right before the write.
                        logger.info(
                            "persist_task_state_dropped_for_cancelled_turn conversation_id=%s keys=%s",
                            conversation_id,
                            sorted(original_updates)[:12],
                        )
                        return
                    self._client(client).table("conversations").update(
                        {"task_state": merged}
                    ).eq("id", conversation_id).eq("org_id", org_id).execute()
                    return
                # Speculative (unconfirmed) run: keep the result for its own reads
                # and replay the original patch only if the run is adopted. The
                # replay is queued under the same lock as the overlay, so
                # concurrent writers replay in the order their overlays merged.
                scope.task_state_overlay[(conversation_id, org_id)] = deepcopy(merged)
                try:
                    patch = deepcopy(original_updates)
                except Exception:  # noqa: BLE001 - non-copyable value: keep the reference
                    patch = dict(original_updates)

                def replay() -> Any:
                    return self._persist_state(conversation_id, org_id, patch, client=client)

                if scope.defer_queued("conversation.task_state", replay):
                    return
            # The replay already finished: write late, outside the lock (the
            # late write takes it, and this thread waits for that write).
            scope.defer("conversation.task_state", replay)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "persist_task_state failed conversation_id=%s error=%s",
                conversation_id,
                exc,
            )

    async def update_task_state(
        self,
        conversation_id: str,
        org_id: str,
        updates: dict[str, Any],
        *,
        client: Any | None = None,
    ) -> None:
        await self._persist_state(conversation_id, org_id, updates, client=client)

    async def compare_and_set_pending_status(
        self,
        conversation_id: str,
        org_id: str,
        *,
        expected_status: str,
        updates: dict[str, Any],
        client: Any | None = None,
        actor_id: str | None = None,
    ) -> bool:
        """SQL compare-and-set on pending_task.status (not a process lock)."""
        from app.services.speculative_execution import block_if_speculative

        # Claiming a pending task consumes an approval: never on unconfirmed speech.
        block_if_speculative("approval.compare_and_set_pending_status")
        token = _read_on_loop.set(True)
        try:
            current = await self.get_task_state(conversation_id, org_id, client=client)
        finally:
            _read_on_loop.reset(token)
        pending = current.get("pending_task") if isinstance(current.get("pending_task"), dict) else {}
        if str(pending.get("status") or "") != str(expected_status or ""):
            return False
        bound = str(pending.get("actor_id") or "").strip()
        requester = str(actor_id or "").strip()
        if bound and requester and bound != requester:
            return False
        claimed = updates.get("pending_task") if isinstance(updates.get("pending_task"), dict) else {}
        claim_id = str(claimed.get("execution_claim_id") or "")
        claimed_at = str(claimed.get("claimed_at") or "")
        db = self._client(client)
        if claim_id:
            try:
                resp = db.rpc(
                    "claim_pending_connector_write",
                    {
                        "p_conversation_id": conversation_id,
                        "p_org_id": org_id,
                        "p_actor_id": requester,
                        "p_expected_status": expected_status,
                        "p_claim_id": claim_id,
                        "p_claimed_at": claimed_at,
                    },
                ).execute()
                row = resp.data
                if row:
                    return True
                if row is None:
                    pass
                else:
                    return False
            except Exception as exc:  # noqa: BLE001
                logger.debug("claim_pending_connector_write rpc skipped: %s", exc)
        from app.services.execution_plan_adapters import enrich_task_state_patch

        patch = enrich_task_state_patch(updates, current_state=current)
        merged = deepcopy(current)
        merged.update(patch)
        if isinstance(patch.get("pending_task"), dict):
            merged["pending_task"] = patch["pending_task"]
        try:
            resp = (
                db.table("conversations")
                .update({"task_state": merged})
                .eq("id", conversation_id)
                .eq("org_id", org_id)
                .filter("task_state->pending_task->>status", "eq", expected_status)
                .execute()
            )
            return bool(getattr(resp, "data", None))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "cas_pending_status failed conversation_id=%s error=%s",
                conversation_id,
                exc,
            )
            return False

    async def ensure_owned_conversation(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str | None,
        title: str = "New conversation",
        client: Any | None = None,
    ) -> str | None:
        """Ensure a conversations row exists for mid-stream task_state writes (STA-306).

        Client-supplied UUIDs are inserted with that id when missing so ReAct write-gate
        persistence is not a silent no-op UPDATE against zero rows.
        """
        conv_id = (conversation_id or "").strip() or None
        uid = (user_id or "").strip()
        if not conv_id or not uid or not org_id:
            return conv_id
        try:
            db = self._client(client)
            # Both round trips run off the event loop (they ran on it, in front
            # of every text turn's first byte); the create guard stays on it.
            owned = await run_io(
                db.table("conversations")
                .select("id")
                .eq("id", conv_id)
                .eq("org_id", org_id)
                .eq("user_id", uid)
                .limit(1)
                .execute
            )
            if owned.data:
                return conv_id
            # Create path only — test credentials default-deny outside isolated org.
            assert_conversation_create_allowed(org_id, actor_id=uid)
            from app.services.speculative_execution import current_scope

            scope = current_scope()
            if scope is not None:
                # Unconfirmed speech never creates a conversation row; adoption replays this.
                scope.defer(
                    "conversation.create",
                    lambda: self.ensure_owned_conversation(
                        org_id=org_id, user_id=uid, conversation_id=conv_id, title=title, client=client
                    ),
                )
                return conv_id
            now = datetime.now(timezone.utc).isoformat()
            safe_title = (title or "New conversation").strip()[:80] or "New conversation"
            await run_io(
                db.table("conversations").insert(
                    {
                        "id": conv_id,
                        "org_id": org_id,
                        "user_id": uid,
                        "title": safe_title,
                        "preview": safe_title[:200],
                        "message_count": 0,
                        "task_state": dict(DEFAULT_TASK_STATE),
                        "created_at": now,
                        "updated_at": now,
                    }
                ).execute
            )
            return conv_id
        except ConversationWriteBlockedError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ensure_owned_conversation failed conversation_id=%s error=%s",
                conv_id,
                exc,
            )
            return conv_id

    async def remember_clarification(
        self,
        conversation_id: str,
        org_id: str,
        parameter: str,
        value: str,
    ) -> None:
        await self.update_task_state(
            conversation_id,
            org_id,
            {"clarified_params": {parameter: value}},
        )

    async def remember_rejected_option(
        self,
        conversation_id: str,
        org_id: str,
        option: str,
    ) -> None:
        await self.update_task_state(
            conversation_id,
            org_id,
            {"rejected_options": [option]},
        )

    async def get_current_plan(
        self,
        conversation_id: str,
        org_id: str,
    ) -> dict[str, Any] | None:
        state = await self.get_task_state(conversation_id, org_id)
        plan = state.get("current_plan")
        return plan if isinstance(plan, dict) else None


_conversation_state_service: ConversationStateService | None = None


def get_conversation_state_service(settings: Settings | None = None) -> ConversationStateService:
    global _conversation_state_service
    if _conversation_state_service is None or settings is not None:
        _conversation_state_service = ConversationStateService(settings)
    return _conversation_state_service
