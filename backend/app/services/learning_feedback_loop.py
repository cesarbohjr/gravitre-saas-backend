"""Learning feedback loop orchestrator over existing v4-v11 systems."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LearningFeedbackLoop:
    """
    Routes outcome feedback to MemoryPromotion, retrieval learning, and company intelligence.
    Does not implement new learning — orchestrates existing subsystems.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def process_feedback(
        self,
        org_id: str,
        feedback_type: str,
        feedback_data: dict[str, Any],
    ) -> None:
        try:
            if feedback_type == "response_quality":
                await self._update_retrieval_signals(org_id, feedback_data)
            elif feedback_type == "action_outcome":
                from app.services.memory_promotion_service import get_memory_promotion_service

                await get_memory_promotion_service(self.settings).detect_outcome_pattern_candidates(org_id)
            elif feedback_type == "approval_decision":
                from app.services.memory_promotion_service import get_memory_promotion_service

                await get_memory_promotion_service(self.settings).detect_decision_pattern_candidates(org_id)
            elif feedback_type == "user_correction":
                await self._update_retrieval_signals(org_id, feedback_data)
        except Exception as exc:  # noqa: BLE001
            logger.debug("learning_feedback_loop_skipped org_id=%s type=%s error=%s", org_id, feedback_type, exc)

    async def _update_retrieval_signals(self, org_id: str, feedback_data: dict[str, Any]) -> None:
        sources = feedback_data.get("sources") or []
        if not sources:
            return
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(self.settings)
        for source in sources[:10]:
            chunk_id = source.get("chunk_id") or source.get("chunkId")
            if not chunk_id:
                continue
            try:
                client.table("rag_chunk_outcomes").upsert(
                    {
                        "org_id": org_id,
                        "chunk_id": chunk_id,
                        "outcome_helpful": feedback_data.get("helpful"),
                    },
                    on_conflict="org_id,chunk_id",
                ).execute()
            except Exception:  # noqa: BLE001
                continue


_learning_feedback_loop: LearningFeedbackLoop | None = None


def get_learning_feedback_loop(settings: Settings | None = None) -> LearningFeedbackLoop:
    global _learning_feedback_loop
    if _learning_feedback_loop is None or settings is not None:
        _learning_feedback_loop = LearningFeedbackLoop(settings)
    return _learning_feedback_loop
