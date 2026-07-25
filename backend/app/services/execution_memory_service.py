"""Execution memory — recall similar successful workflow/orchestration patterns (Tier 1)."""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

_TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text or "")}


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


class ExecutionMemoryService:
    """Stores and retrieves operational execution patterns for plan hints."""

    TABLE = "intelligence_outcome_events"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def record_orchestration_pattern(
        self,
        *,
        org_id: str,
        goal: str,
        steps: list[dict[str, Any]],
        success: bool,
        run_id: str | None = None,
    ) -> None:
        if not goal.strip() or not steps:
            return
        try:
            step_labels = [str(s.get("label") or s.get("segment") or "") for s in steps[:12]]
            metadata = {
                "execution_pattern": True,
                "goal": goal[:500],
                "step_labels": step_labels,
                "step_count": len(steps),
                "success": success,
                "run_id": run_id,
            }
            self._client().table(self.TABLE).insert(
                {
                    "id": str(uuid4()),
                    "org_id": org_id,
                    "outcome_event": "workflow_executed" if success else "workflow_failed",
                    "entity_type": "execution_pattern",
                    "entity_id": str(run_id or uuid4()),
                    "metadata": metadata,
                    "task_type": "orchestration",
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("execution_memory_record_skipped org_id=%s error=%s", org_id, exc)

    async def find_similar_patterns(
        self,
        org_id: str,
        query: str,
        *,
        limit: int = 3,
        min_score: float = 0.18,
    ) -> list[dict[str, Any]]:
        try:
            resp = (
                self._client()
                .table(self.TABLE)
                .select("metadata, outcome_event, created_at, entity_id")
                .eq("org_id", org_id)
                .eq("entity_type", "execution_pattern")
                .order("created_at", desc=True)
                .limit(40)
                .execute()
            )
            rows = list(resp.data or [])
        except Exception as exc:  # noqa: BLE001
            logger.debug("execution_memory_query_skipped org_id=%s error=%s", org_id, exc)
            return []

        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            meta = row.get("metadata") or {}
            if not meta.get("execution_pattern"):
                continue
            goal = str(meta.get("goal") or "")
            score = _similarity(query, goal)
            if score < min_score:
                continue
            if row.get("outcome_event") == "workflow_failed" and not meta.get("success"):
                score *= 0.5
            scored.append(
                (
                    score,
                    {
                        "goal": goal,
                        "step_labels": list(meta.get("step_labels") or []),
                        "step_count": meta.get("step_count"),
                        "success": meta.get("success", True),
                        "score": round(score, 3),
                        "run_id": meta.get("run_id"),
                    },
                )
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def format_hint_for_plan(self, patterns: list[dict[str, Any]]) -> str:
        if not patterns:
            return ""
        best = patterns[0]
        labels = ", ".join(str(x) for x in (best.get("step_labels") or [])[:5] if x)
        if not labels:
            return ""
        return (
            f"Similar successful run ({int((best.get('score') or 0) * 100)}% match): "
            f"\"{best.get('goal')}\" used steps: {labels}."
        )

    async def recall_recent_workflow_outcomes(
        self,
        org_id: str,
        *,
        limit: int = 8,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """Module A outcomes for canvas/chat unification (Phase 3).

        Reads the same ``intelligence_outcome_events`` rows finalize_execution_outcome
        writes — no canvas-specific parallel store.
        """
        try:
            resp = (
                self._client()
                .table(self.TABLE)
                .select(
                    "outcome_event, workflow_id, workflow_run_id, metadata, created_at, entity_type"
                )
                .eq("org_id", org_id)
                .order("created_at", desc=True)
                .limit(40)
                .execute()
            )
            rows = list(resp.data or [])
        except Exception as exc:  # noqa: BLE001
            logger.debug("workflow_outcome_recall_skipped org_id=%s error=%s", org_id, exc)
            return []

        out: list[dict[str, Any]] = []
        q_tokens = _tokenize(query or "")
        for row in rows:
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            source = str(meta.get("source") or "")
            # Prefer terminal workflow outcomes from any surface (canvas/worker/api/chat).
            entity_type = str(row.get("entity_type") or "")
            if entity_type == "execution_pattern":
                continue
            status = str(meta.get("terminal_status") or row.get("outcome_event") or "")
            summary = str(meta.get("verified_summary") or meta.get("error") or status)
            wf_id = str(row.get("workflow_id") or "")
            run_id = str(row.get("workflow_run_id") or meta.get("run_id") or "")
            blob = f"{summary} {wf_id} {source} {status}"
            if q_tokens and _similarity(query or "", blob) < 0.08 and not any(
                t in blob.lower() for t in ("workflow", "morning", "run", "canvas", "schedule")
            ):
                # Keep high-signal recent rows even without query overlap when asking
                # about workflows generally — filter only when query has no workflow cues.
                if not (q_tokens & {"workflow", "run", "morning", "canvas", "schedule", "failed", "complete", "completed"}):
                    continue
            out.append(
                {
                    "workflow_id": wf_id or None,
                    "run_id": run_id or None,
                    "status": status,
                    "source": source or None,
                    "summary": summary[:300],
                    "created_at": row.get("created_at"),
                    "outcome_event": row.get("outcome_event"),
                }
            )
            if len(out) >= limit:
                break
        return out

    def format_workflow_outcomes_for_prompt(self, outcomes: list[dict[str, Any]]) -> str:
        if not outcomes:
            return ""
        lines = []
        for row in outcomes[:6]:
            src = row.get("source") or "unknown"
            st = row.get("status") or row.get("outcome_event") or "?"
            rid = (row.get("run_id") or "")[:8]
            wfid = (row.get("workflow_id") or "")[:8]
            summary = str(row.get("summary") or "")[:120]
            lines.append(
                f"- [{src}] workflow={wfid or 'n/a'} run={rid or 'n/a'} status={st}: {summary}"
            )
        return (
            "<recent_workflow_outcomes>\n"
            + "\n".join(lines)
            + "\n</recent_workflow_outcomes>\n"
            "These are real Module A outcomes (canvas and chat share this record). "
            "Answer status questions from them; do not redirect to the Runs page unless asked."
        )


_service: ExecutionMemoryService | None = None


def get_execution_memory_service(settings: Settings | None = None) -> ExecutionMemoryService:
    global _service
    if _service is None or settings is not None:
        _service = ExecutionMemoryService(settings)
    return _service
