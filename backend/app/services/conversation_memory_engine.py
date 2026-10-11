"""Conversation memory — preferences, rejections, and action outcomes across chat turns."""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.conversation_state_service import get_conversation_state_service
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

_MEMORY_KEY = "conversation_memory"
_MAX_ITEMS = 20


def _empty_memory() -> dict[str, Any]:
    return {
        "preferences": {},
        "rejected_recommendations": [],
        "successful_actions": [],
        "failed_actions": [],
        "preferred_connectors": [],
        "preferred_workflows": [],
        "communication_style": None,
    }


class ConversationMemoryEngine:
    """Memory-aware conversation layer built on conversation task_state."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._state = get_conversation_state_service(self.settings)

    async def build_context_profile(
        self,
        *,
        org_id: str,
        user_id: str,
        conversation_id: str,
        query: str,
        client: Any | None = None,
    ) -> dict[str, Any]:
        memory = await self.get_memory(org_id, user_id, conversation_id, client=client)
        relevant = self._select_relevant(memory, query)
        return {
            "memory": memory,
            "relevant": relevant,
            "suppressed_suggestion_keys": self._suppression_keys(memory),
            "prompt_section": self.build_prompt_section(relevant),
        }

    async def get_memory(
        self,
        org_id: str,
        user_id: str,
        conversation_id: str,
        *,
        client: Any | None = None,
    ) -> dict[str, Any]:
        state = await self._state.get_task_state(conversation_id, org_id, client=client)
        raw = state.get(_MEMORY_KEY)
        if not isinstance(raw, dict):
            return _empty_memory()
        merged = _empty_memory()
        merged.update(raw)
        return merged

    async def record_preference(
        self,
        conversation_id: str,
        org_id: str,
        key: str,
        value: Any,
        *,
        client: Any | None = None,
    ) -> None:
        def change(memory: dict[str, Any]) -> None:
            prefs = safe_normalize_stored_dict(memory, key="preferences")
            prefs[key] = value
            memory["preferences"] = prefs

        await self._change_memory(conversation_id, org_id, change, client=client)

    async def record_rejection(
        self,
        conversation_id: str,
        org_id: str,
        recommendation: str,
        *,
        reason: str | None = None,
        client: Any | None = None,
    ) -> None:
        def change(memory: dict[str, Any]) -> None:
            rejected = list(memory.get("rejected_recommendations") or [])
            fingerprint = self._fingerprint(recommendation)
            if not any(self._fingerprint(row.get("text", "")) == fingerprint for row in rejected):
                rejected.append({"text": recommendation[:500], "reason": reason})
            memory["rejected_recommendations"] = rejected[-_MAX_ITEMS:]

        await self._change_memory(conversation_id, org_id, change, client=client)
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {"rejected_options": [recommendation[:200]]},
            client=client,
        )

    async def record_action_outcome(
        self,
        conversation_id: str,
        org_id: str,
        *,
        action: str,
        success: bool,
        connector: str | None = None,
        client: Any | None = None,
    ) -> None:
        def change(memory: dict[str, Any]) -> None:
            bucket_key = "successful_actions" if success else "failed_actions"
            bucket = list(memory.get(bucket_key) or [])
            bucket.append({"action": action[:300], "connector": connector})
            memory[bucket_key] = bucket[-_MAX_ITEMS:]
            if success and connector:
                preferred = list(memory.get("preferred_connectors") or [])
                if connector not in preferred:
                    preferred.append(connector)
                memory["preferred_connectors"] = preferred[-_MAX_ITEMS:]

        await self._change_memory(conversation_id, org_id, change, client=client)

    def build_prompt_section(self, relevant: dict[str, Any]) -> str:
        lines: list[str] = []
        prefs = relevant.get("preferences") or {}
        if prefs:
            lines.append("User preferences: " + ", ".join(f"{k}={v}" for k, v in list(prefs.items())[:6]))
        rejected = relevant.get("rejected_recommendations") or []
        if rejected:
            lines.append(
                "Previously rejected (do not repeat): "
                + "; ".join(str(row.get("text") or "")[:80] for row in rejected[:5])
            )
        successes = relevant.get("successful_actions") or []
        if successes:
            lines.append(
                "Recent successful actions: "
                + "; ".join(str(row.get("action") or "")[:80] for row in successes[-3:])
            )
        failures = relevant.get("failed_actions") or []
        if failures:
            lines.append(
                "Recent failed actions (avoid repeating without new data): "
                + "; ".join(str(row.get("action") or "")[:80] for row in failures[-3:])
            )
        preferred_connectors = relevant.get("preferred_connectors") or []
        if preferred_connectors:
            lines.append("Preferred connectors: " + ", ".join(preferred_connectors[:8]))
        style = relevant.get("communication_style")
        if style:
            lines.append(f"Communication style: {style}")
        if not lines:
            return ""
        return "<conversation_memory>\n" + "\n".join(lines) + "\n</conversation_memory>"

    async def _change_memory(
        self,
        conversation_id: str,
        org_id: str,
        change: Callable[[dict[str, Any]], None],
        *,
        client: Any | None = None,
    ) -> None:
        """Edit the stored memory in one locked read-change-write.

        The change runs on the memory read under the conversation lock, so a
        failed read never saves defaults over real memory, and two writers in
        the same moment both keep their entries.
        """
        if not conversation_id or not org_id:
            return

        def build_patch(state: dict[str, Any]) -> dict[str, Any]:
            raw = state.get(_MEMORY_KEY)
            memory = _empty_memory()
            if isinstance(raw, dict):
                memory.update(raw)
            change(memory)
            return {_MEMORY_KEY: memory}

        await self._state.update_task_state_from(conversation_id, org_id, build_patch, client=client)

    @staticmethod
    def _fingerprint(text: str) -> str:
        return hashlib.sha256(text.strip().lower().encode()).hexdigest()[:16]

    def _suppression_keys(self, memory: dict[str, Any]) -> list[str]:
        keys: list[str] = []
        for row in memory.get("rejected_recommendations") or []:
            text = str(row.get("text") or "")
            if text:
                keys.append(f"rejected_{self._fingerprint(text)}")
        return keys

    def _select_relevant(self, memory: dict[str, Any], query: str) -> dict[str, Any]:
        lowered = query.lower()
        relevant = dict(memory)
        rejected = [
            row
            for row in memory.get("rejected_recommendations") or []
            if any(token in str(row.get("text") or "").lower() for token in lowered.split()[:6])
            or len(memory.get("rejected_recommendations") or []) <= 5
        ]
        if rejected:
            relevant["rejected_recommendations"] = rejected[:5]
        return relevant


_engine: ConversationMemoryEngine | None = None


def get_conversation_memory_engine(settings: Settings | None = None) -> ConversationMemoryEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = ConversationMemoryEngine(settings)
    return _engine
