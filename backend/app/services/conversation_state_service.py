"""Structured multi-turn task state within a conversation thread."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

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
    ) -> dict[str, Any]:
        if not conversation_id or not org_id:
            return deepcopy(DEFAULT_TASK_STATE)
        try:
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
            if rows:
                return self._normalize_state(rows[0].get("task_state"))
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "get_task_state fallback conversation_id=%s error=%s",
                conversation_id,
                exc,
            )
        return deepcopy(DEFAULT_TASK_STATE)

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
        try:
            current = await self.get_task_state(conversation_id, org_id, client=client)
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
                else:
                    merged[key] = value
            self._client(client).table("conversations").update(
                {"task_state": merged}
            ).eq("id", conversation_id).eq("org_id", org_id).execute()
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
            owned = (
                db.table("conversations")
                .select("id")
                .eq("id", conv_id)
                .eq("org_id", org_id)
                .eq("user_id", uid)
                .limit(1)
                .execute()
            )
            if owned.data:
                return conv_id
            now = datetime.now(timezone.utc).isoformat()
            safe_title = (title or "New conversation").strip()[:80] or "New conversation"
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
            ).execute()
            return conv_id
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
