"""v4 Agent Memory Layer — controlled promotion into agent_memories with full audit trail."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.rag.embedding import get_embedding
from app.services.query_normalization import normalize_query
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

V4_PROVENANCE_PREFIX = "v4:"
AUTO_GLOSSARY_PROVENANCE = f"{V4_PROVENANCE_PREFIX}auto:glossary"
MANUAL_GLOSSARY_PROVENANCE = f"{V4_PROVENANCE_PREFIX}manual:glossary"
MANUAL_WORKFLOW_PROVENANCE = f"{V4_PROVENANCE_PREFIX}manual:workflow_pattern"
MANUAL_RESPONSE_PROVENANCE = f"{V4_PROVENANCE_PREFIX}manual:successful_response"
MANUAL_OUTCOME_PROVENANCE = f"{V4_PROVENANCE_PREFIX}manual:outcome_pattern"
MANUAL_DECISION_PROVENANCE = f"{V4_PROVENANCE_PREFIX}manual:decision_pattern"

PENDING_MIN_FREQUENCY = 5


class MemoryPromotionStatus(str, Enum):
    CANDIDATE = "candidate"
    AUTO_PROMOTED = "auto_promoted"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    WRITTEN = "written"
    EXPIRED = "expired"
    ROLLED_BACK = "rolled_back"


class MemoryPromotionService:
    """Single write path for v4-originated agent_memories content."""

    AUTO_PROMOTE_MIN_OCCURRENCES = 20
    AUTO_PROMOTE_MIN_DEPARTMENTS = 2
    AUTO_PROMOTED_TTL_DAYS = 90
    USAGE_DECAY_DAYS = 30

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    @staticmethod
    def content_fingerprint(
        org_id: str,
        source_table: str,
        source_id: str | None,
        content: str,
    ) -> str:
        raw = f"{org_id}|{source_table}|{source_id or ''}|{normalize_query(content)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def is_v4_provenance(provenance: str | None) -> bool:
        return bool(provenance and str(provenance).startswith(V4_PROVENANCE_PREFIX))

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _count_departments_for_term(self, client: Any, org_id: str, term: str) -> int:
        term_key = normalize_query(term)
        if not term_key:
            return 0
        rows = (
            client.table("user_query_patterns")
            .select("department, query_text, normalized_query_text")
            .eq("org_id", org_id)
            .limit(2000)
            .execute()
            .data
            or []
        )
        departments: set[str] = set()
        for row in rows:
            haystack = normalize_query(
                f"{row.get('normalized_query_text') or ''} {row.get('query_text') or ''}"
            )
            dept = str(row.get("department") or "").strip()
            if dept and term_key in haystack:
                departments.add(dept)
        return len(departments)

    def _agents_for_departments(
        self, client: Any, org_id: str, departments: set[str]
    ) -> list[str]:
        if not departments:
            return []
        agent_ids: list[str] = []
        for dept in sorted(departments):
            rows = (
                client.table("agents")
                .select("id")
                .eq("org_id", org_id)
                .eq("department", dept)
                .limit(5)
                .execute()
                .data
                or []
            )
            agent_ids.extend(str(row["id"]) for row in rows if row.get("id"))
        return list(dict.fromkeys(agent_ids))[:10]

    def _departments_for_term(self, client: Any, org_id: str, term: str) -> set[str]:
        term_key = normalize_query(term)
        rows = (
            client.table("user_query_patterns")
            .select("department, query_text, normalized_query_text")
            .eq("org_id", org_id)
            .limit(2000)
            .execute()
            .data
            or []
        )
        departments: set[str] = set()
        for row in rows:
            haystack = normalize_query(
                f"{row.get('normalized_query_text') or ''} {row.get('query_text') or ''}"
            )
            dept = str(row.get("department") or "").strip()
            if dept and term_key in haystack:
                departments.add(dept)
        return departments

    def _is_rejected_fingerprint(self, client: Any, org_id: str, fingerprint: str) -> bool:
        rows = (
            client.table("memory_promotion_candidates")
            .select("id")
            .eq("org_id", org_id)
            .eq("content_fingerprint", fingerprint)
            .eq("status", MemoryPromotionStatus.REJECTED.value)
            .limit(1)
            .execute()
            .data
            or []
        )
        return bool(rows)

    def _upsert_candidate(
        self,
        client: Any,
        *,
        org_id: str,
        source_table: str,
        source_id: str | None,
        candidate_type: str,
        content: str,
        memory_category: str,
        status: str,
        frequency: int,
        department_count: int,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        fingerprint = self.content_fingerprint(org_id, source_table, source_id, content)
        if self._is_rejected_fingerprint(client, org_id, fingerprint):
            return {}
        now = self._now().isoformat()
        payload = {
            "org_id": org_id,
            "source_table": source_table,
            "source_id": source_id,
            "candidate_type": candidate_type,
            "content": content,
            "memory_category": memory_category,
            "status": status,
            "frequency": frequency,
            "department_count": department_count,
            "metadata": metadata,
            "content_fingerprint": fingerprint,
            "updated_at": now,
        }
        existing = (
            client.table("memory_promotion_candidates")
            .select("*")
            .eq("org_id", org_id)
            .eq("content_fingerprint", fingerprint)
            .limit(1)
            .execute()
            .data
            or []
        )
        if existing:
            row = existing[0]
            if row.get("status") in {
                MemoryPromotionStatus.WRITTEN.value,
                MemoryPromotionStatus.REJECTED.value,
                MemoryPromotionStatus.ROLLED_BACK.value,
            }:
                return row
            updated = (
                client.table("memory_promotion_candidates")
                .update(payload)
                .eq("id", row["id"])
                .execute()
            )
            return updated.data[0] if updated.data else row
        payload["created_at"] = now
        inserted = client.table("memory_promotion_candidates").insert(payload).execute()
        return inserted.data[0] if inserted.data else payload

    def _build_glossary_reasoning(
        self,
        *,
        term: str,
        frequency: int,
        department_count: int,
        auto: bool,
    ) -> tuple[str, dict[str, Any]]:
        snapshot = {
            "term": term,
            "frequency": frequency,
            "department_count": department_count,
            "min_occurrences": self.AUTO_PROMOTE_MIN_OCCURRENCES,
            "min_departments": self.AUTO_PROMOTE_MIN_DEPARTMENTS,
            "auto_promoted": auto,
        }
        if auto:
            reasoning = (
                f"Term '{term}' seen {frequency} times across {department_count} distinct "
                f"department(s), exceeding the {self.AUTO_PROMOTE_MIN_OCCURRENCES}-occurrence / "
                f"{self.AUTO_PROMOTE_MIN_DEPARTMENTS}-department auto-promotion threshold."
            )
        else:
            reasoning = (
                f"Term '{term}' flagged for review with frequency {frequency} and "
                f"{department_count} department(s); below auto-promotion threshold "
                f"({self.AUTO_PROMOTE_MIN_OCCURRENCES} occurrences, "
                f"{self.AUTO_PROMOTE_MIN_DEPARTMENTS} departments required)."
            )
        return reasoning, snapshot

    def _write_memories(
        self,
        client: Any,
        *,
        org_id: str,
        agent_ids: list[str],
        content: str,
        category: str,
        provenance: str,
        confidence: float,
        expires_at: datetime | None,
        editable: bool,
    ) -> list[str]:
        memory_ids: list[str] = []
        text = content.strip()
        embedding = get_embedding(text, self.settings, org_id=org_id)
        for agent_id in agent_ids:
            payload: dict[str, Any] = {
                "org_id": org_id,
                "agent_id": agent_id,
                "content": text,
                "category": category,
                "provenance": provenance,
                "confidence": max(0, min(100, float(confidence))),
                "editable": editable,
                "embedding": embedding,
                "is_active": True,
                "expires_at": expires_at.isoformat() if expires_at else None,
            }
            inserted = client.table("agent_memories").insert(payload).execute()
            if inserted.data:
                memory_ids.append(str(inserted.data[0]["id"]))
        return memory_ids

    def _record_audit(
        self,
        client: Any,
        *,
        org_id: str,
        memory_id: str | None,
        candidate_id: str | None,
        source_table: str,
        source_id: str | None,
        promotion_path: str,
        decision_reasoning: str,
        threshold_snapshot: dict[str, Any],
        status_at_decision: str,
        decided_by: str | None = None,
        action: str = "promote",
    ) -> dict[str, Any]:
        payload = {
            "org_id": org_id,
            "memory_id": memory_id,
            "candidate_id": candidate_id,
            "source_table": source_table,
            "source_id": source_id,
            "promotion_path": promotion_path,
            "decision_reasoning": decision_reasoning,
            "threshold_snapshot": threshold_snapshot,
            "decided_by": decided_by,
            "status_at_decision": status_at_decision,
            "action": action,
            "decided_at": self._now().isoformat(),
        }
        inserted = client.table("agent_memory_promotion_audit").insert(payload).execute()
        return inserted.data[0] if inserted.data else payload

    def _promote_candidate(
        self,
        client: Any,
        candidate: dict[str, Any],
        *,
        org_id: str,
        promotion_path: str,
        decision_reasoning: str,
        threshold_snapshot: dict[str, Any],
        provenance: str,
        expires_at: datetime | None,
        decided_by: str | None = None,
        status_at_decision: str,
    ) -> dict[str, Any]:
        if promotion_path == "auto" and str(candidate.get("candidate_type") or "") != "glossary":
            raise ValueError("Only glossary candidates may be auto-promoted")
        departments = set(candidate.get("metadata", {}).get("departments") or [])
        if not departments and candidate.get("metadata", {}).get("term"):
            departments = self._departments_for_term(
                client, org_id, str(candidate["metadata"]["term"])
            )
        agent_ids = self._agents_for_departments(client, org_id, departments)
        if not agent_ids:
            raise ValueError("No agents found in associated departments for memory promotion")

        memory_ids = self._write_memories(
            client,
            org_id=org_id,
            agent_ids=agent_ids,
            content=str(candidate["content"]),
            category=str(candidate.get("memory_category") or "fact"),
            provenance=provenance,
            confidence=85.0 if promotion_path == "auto" else 95.0,
            expires_at=expires_at,
            editable=promotion_path != "auto",
        )
        for memory_id in memory_ids:
            self._record_audit(
                client,
                org_id=org_id,
                memory_id=memory_id,
                candidate_id=str(candidate.get("id")) if candidate.get("id") else None,
                source_table=str(candidate.get("source_table") or ""),
                source_id=str(candidate.get("source_id")) if candidate.get("source_id") else None,
                promotion_path=promotion_path,
                decision_reasoning=decision_reasoning,
                threshold_snapshot=threshold_snapshot,
                status_at_decision=status_at_decision,
                decided_by=decided_by,
            )

        update_payload = {
            "status": MemoryPromotionStatus.WRITTEN.value,
            "memory_ids": memory_ids,
            "updated_at": self._now().isoformat(),
        }
        if candidate.get("id"):
            client.table("memory_promotion_candidates").update(update_payload).eq(
                "id", candidate["id"]
            ).execute()

        if candidate.get("source_table") == "org_glossary_terms" and candidate.get("source_id"):
            client.table("org_glossary_terms").update(
                {"status": "confirmed", "last_extracted_at": self._now().isoformat()}
            ).eq("id", candidate["source_id"]).execute()

        return {"candidate_id": candidate.get("id"), "memory_ids": memory_ids}

    async def evaluate_glossary_candidates(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        terms = (
            client.table("org_glossary_terms")
            .select("*")
            .eq("org_id", org_id)
            .eq("status", "candidate")
            .execute()
            .data
            or []
        )
        auto_promoted = 0
        pending = 0
        skipped = 0
        for term_row in terms:
            term = str(term_row.get("term") or "")
            frequency = int(term_row.get("frequency") or 0)
            dept_count = self._count_departments_for_term(client, org_id, term)
            departments = sorted(self._departments_for_term(client, org_id, term))
            content = (
                f"Company term '{term}' ({term_row.get('term_type') or 'term'}): "
                f"internal vocabulary used in {frequency} logged interactions."
            )
            metadata = {
                "term": term,
                "term_type": term_row.get("term_type"),
                "departments": departments,
            }
            meets_auto = (
                frequency >= self.AUTO_PROMOTE_MIN_OCCURRENCES
                and dept_count >= self.AUTO_PROMOTE_MIN_DEPARTMENTS
            )
            if meets_auto:
                reasoning, snapshot = self._build_glossary_reasoning(
                    term=term,
                    frequency=frequency,
                    department_count=dept_count,
                    auto=True,
                )
                candidate = self._upsert_candidate(
                    client,
                    org_id=org_id,
                    source_table="org_glossary_terms",
                    source_id=str(term_row["id"]),
                    candidate_type="glossary",
                    content=content,
                    memory_category="fact",
                    status=MemoryPromotionStatus.AUTO_PROMOTED.value,
                    frequency=frequency,
                    department_count=dept_count,
                    metadata=metadata,
                )
                if not candidate:
                    skipped += 1
                    continue
                try:
                    expires_at = self._now() + timedelta(days=self.AUTO_PROMOTED_TTL_DAYS)
                    self._promote_candidate(
                        client,
                        candidate,
                        org_id=org_id,
                        promotion_path="auto",
                        decision_reasoning=reasoning,
                        threshold_snapshot=snapshot,
                        provenance=AUTO_GLOSSARY_PROVENANCE,
                        expires_at=expires_at,
                        status_at_decision=MemoryPromotionStatus.AUTO_PROMOTED.value,
                    )
                    auto_promoted += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "glossary_auto_promote_failed org_id=%s term=%s error=%s",
                        org_id,
                        term,
                        exc,
                    )
                    self._upsert_candidate(
                        client,
                        org_id=org_id,
                        source_table="org_glossary_terms",
                        source_id=str(term_row["id"]),
                        candidate_type="glossary",
                        content=content,
                        memory_category="fact",
                        status=MemoryPromotionStatus.PENDING_APPROVAL.value,
                        frequency=frequency,
                        department_count=dept_count,
                        metadata=metadata,
                    )
                    pending += 1
            elif frequency >= PENDING_MIN_FREQUENCY:
                self._upsert_candidate(
                    client,
                    org_id=org_id,
                    source_table="org_glossary_terms",
                    source_id=str(term_row["id"]),
                    candidate_type="glossary",
                    content=content,
                    memory_category="fact",
                    status=MemoryPromotionStatus.PENDING_APPROVAL.value,
                    frequency=frequency,
                    department_count=dept_count,
                    metadata=metadata,
                )
                pending += 1
            else:
                skipped += 1
        return {
            "org_id": org_id,
            "glossary_evaluated": len(terms),
            "auto_promoted": auto_promoted,
            "pending_approval": pending,
            "skipped": skipped,
        }

    async def detect_workflow_pattern_candidates(self, org_id: str) -> list[dict[str, Any]]:
        """Minimal rule: same workflow failed 3+ times in the last 30 days."""
        client = self._client()
        since = (self._now() - timedelta(days=30)).isoformat()
        runs = (
            client.table("workflow_runs")
            .select("workflow_id, status, error_message")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .execute()
            .data
            or []
        )
        failures: dict[str, list[str]] = {}
        for row in runs:
            if str(row.get("status") or "").lower() != "failed":
                continue
            wf_id = str(row.get("workflow_id") or "")
            if not wf_id:
                continue
            failures.setdefault(wf_id, []).append(str(row.get("error_message") or "unknown error"))

        created: list[dict[str, Any]] = []
        for wf_id, errors in failures.items():
            if len(errors) < 3:
                continue
            content = (
                f"Workflow {wf_id} has failed {len(errors)} times in the last 30 days. "
                f"Most recent error: {errors[-1][:200]}"
            )
            candidate = self._upsert_candidate(
                client,
                org_id=org_id,
                source_table="workflow_pattern",
                source_id=None,
                candidate_type="workflow_pattern",
                content=content,
                memory_category="pattern",
                status=MemoryPromotionStatus.PENDING_APPROVAL.value,
                frequency=len(errors),
                department_count=0,
                metadata={"workflow_id": wf_id, "failure_count": len(errors)},
            )
            if candidate:
                created.append(candidate)
        return created

    async def detect_successful_response_candidates(self, org_id: str) -> list[dict[str, Any]]:
        """Helpful feedback + quality score, grouped by normalized query (3+ times)."""
        client = self._client()
        rows = (
            client.table("user_query_patterns")
            .select("normalized_query_text, query_text, feedback_helpful, rag_quality_score")
            .eq("org_id", org_id)
            .eq("feedback_helpful", True)
            .execute()
            .data
            or []
        )
        grouped: dict[str, int] = {}
        for row in rows:
            score = float(row.get("rag_quality_score") or 0.0)
            if score < 0.7:
                continue
            key = normalize_query(
                str(row.get("normalized_query_text") or row.get("query_text") or "")
            )
            if key:
                grouped[key] = grouped.get(key, 0) + 1

        created: list[dict[str, Any]] = []
        for query_text, count in grouped.items():
            if count < 3:
                continue
            content = (
                f"Users marked answers to '{query_text}' as helpful {count} times "
                f"(rag_quality_score >= 0.7). Consider retaining this as durable knowledge."
            )
            fingerprint = self.content_fingerprint(org_id, "successful_response", None, content)
            candidate = self._upsert_candidate(
                client,
                org_id=org_id,
                source_table="successful_response",
                source_id=None,
                candidate_type="successful_response",
                content=content,
                memory_category="fact",
                status=MemoryPromotionStatus.PENDING_APPROVAL.value,
                frequency=count,
                department_count=0,
                metadata={"normalized_query": query_text, "helpful_count": count},
            )
            if candidate:
                created.append(candidate)
        return created

    async def detect_outcome_pattern_candidates(self, org_id: str) -> list[dict[str, Any]]:
        """v8: correlational outcome patterns — always pending_approval."""
        from app.services.outcome_attribution_service import (
            MIN_SAMPLE_SIZE,
            get_outcome_attribution_service,
        )

        outcome_service = get_outcome_attribution_service(self.settings)
        client = self._client()
        agents = (
            client.table("agents")
            .select("id, name")
            .eq("org_id", org_id)
            .limit(200)
            .execute()
            .data
            or []
        )
        created: list[dict[str, Any]] = []
        for agent in agents:
            agent_id = str(agent.get("id") or "")
            if not agent_id:
                continue
            summary = await outcome_service.get_agent_outcome_summary(org_id, agent_id)
            if not summary.get("sufficientData"):
                continue
            win_rate = float(summary.get("winRate") or 0.0)
            sample_size = int(summary.get("sampleSize") or 0)
            if win_rate < 0.55:
                continue
            content = (
                f"Agent {agent.get('name') or agent_id}'s deal actions correlate with positive "
                f"deal_amount changes in {win_rate:.0%} of {sample_size} observed cases "
                f"(correlational only)."
            )
            candidate = self._upsert_candidate(
                client,
                org_id=org_id,
                source_table="outcome_pattern",
                source_id=None,
                candidate_type="outcome_pattern",
                content=content,
                memory_category="pattern",
                status=MemoryPromotionStatus.PENDING_APPROVAL.value,
                frequency=sample_size,
                department_count=0,
                metadata={
                    "agent_id": agent_id,
                    "win_rate": win_rate,
                    "sample_size": sample_size,
                    "avg_metric_delta": summary.get("avgMetricDelta"),
                },
            )
            if candidate:
                created.append(candidate)
        return created

    async def detect_decision_pattern_candidates(self, org_id: str) -> list[dict[str, Any]]:
        """v11: approval/rejection patterns over structured fields — always pending_approval."""
        MIN_DECISIONS_FOR_PATTERN = 15
        decisions = await self._load_recent_decisions(org_id)
        if len(decisions) < MIN_DECISIONS_FOR_PATTERN:
            return []

        patterns = self._detect_threshold_patterns(decisions)
        created: list[dict[str, Any]] = []
        client = self._client()
        for pattern in patterns:
            if int(pattern.get("sample_size") or 0) < MIN_DECISIONS_FOR_PATTERN:
                continue
            content = str(pattern.get("pattern_description") or "")
            if not content:
                continue
            candidate = self._upsert_candidate(
                client,
                org_id=org_id,
                source_table="decision_pattern",
                source_id=None,
                candidate_type="decision_pattern",
                content=content,
                memory_category="rule",
                status=MemoryPromotionStatus.PENDING_APPROVAL.value,
                frequency=int(pattern.get("sample_size") or 0),
                department_count=0,
                metadata={
                    "evidence": pattern.get("evidence") or {},
                    "sample_size": pattern.get("sample_size"),
                },
            )
            if candidate:
                created.append(candidate)
        return created

    async def _load_recent_decisions(self, org_id: str) -> list[dict[str, Any]]:
        since = (self._now() - timedelta(days=30)).isoformat()
        client = self._client()
        rows = (
            client.table("approvals")
            .select("id, type, priority, status, context, reviewed_at")
            .eq("org_id", org_id)
            .in_("status", ["approved", "rejected"])
            .gte("reviewed_at", since)
            .limit(500)
            .execute()
            .data
            or []
        )
        return rows

    def _detect_threshold_patterns(self, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Simple threshold detection on type and priority fields confirmed in approvals schema."""
        patterns: list[dict[str, Any]] = []
        for field in ("type", "priority"):
            grouped: dict[str, list[str]] = {}
            for row in decisions:
                key = str(row.get(field) or "").strip().lower()
                if not key:
                    continue
                grouped.setdefault(key, []).append(str(row.get("status") or "").lower())
            for key, statuses in grouped.items():
                if len(statuses) < 15:
                    continue
                approved = sum(1 for s in statuses if s == "approved")
                rejected = len(statuses) - approved
                dominant = "approved" if approved >= rejected else "rejected"
                dominant_count = approved if dominant == "approved" else rejected
                rate = dominant_count / len(statuses)
                if rate < 0.8:
                    continue
                patterns.append(
                    {
                        "pattern_description": (
                            f"Approvals with {field}={key!r} were {dominant} "
                            f"{dominant_count}/{len(statuses)} times in the last 30 days"
                        ),
                        "evidence": {
                            "field": field,
                            "value": key,
                            "dominant_outcome": dominant,
                            "dominant_count": dominant_count,
                            "total": len(statuses),
                        },
                        "sample_size": len(statuses),
                    }
                )
        return patterns

    async def run_evaluation(self, org_id: str) -> dict[str, Any]:
        glossary = await self.evaluate_glossary_candidates(org_id)
        workflow = await self.detect_workflow_pattern_candidates(org_id)
        responses = await self.detect_successful_response_candidates(org_id)
        outcomes = await self.detect_outcome_pattern_candidates(org_id)
        decisions = await self.detect_decision_pattern_candidates(org_id)
        return {
            "glossary": glossary,
            "workflow_patterns_detected": len(workflow),
            "successful_responses_detected": len(responses),
            "outcome_patterns_detected": len(outcomes),
            "decision_patterns_detected": len(decisions),
        }

    async def approve_candidate(
        self,
        candidate_id: str,
        org_id: str,
        approved_by_user_id: str,
    ) -> dict[str, Any]:
        client = self._client()
        rows = (
            client.table("memory_promotion_candidates")
            .select("*")
            .eq("id", candidate_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("Promotion candidate not found")
        candidate = rows[0]
        if candidate.get("status") == MemoryPromotionStatus.REJECTED.value:
            raise ValueError("Cannot approve a rejected candidate")
        if candidate.get("status") == MemoryPromotionStatus.WRITTEN.value:
            return {"candidate_id": candidate_id, "memory_ids": candidate.get("memory_ids") or []}

        candidate_type = str(candidate.get("candidate_type") or "")
        if candidate_type not in {
            "glossary",
            "workflow_pattern",
            "successful_response",
            "outcome_pattern",
            "decision_pattern",
        }:
            raise ValueError("Unsupported candidate type")

        provenance_map = {
            "glossary": MANUAL_GLOSSARY_PROVENANCE,
            "workflow_pattern": MANUAL_WORKFLOW_PROVENANCE,
            "successful_response": MANUAL_RESPONSE_PROVENANCE,
            "outcome_pattern": MANUAL_OUTCOME_PROVENANCE,
            "decision_pattern": MANUAL_DECISION_PROVENANCE,
        }
        reasoning = (
            f"Manually approved {candidate_type} candidate after human review "
            f"(frequency={candidate.get('frequency')}, departments={candidate.get('department_count')})."
        )
        snapshot = {
            "candidate_type": candidate_type,
            "frequency": candidate.get("frequency"),
            "department_count": candidate.get("department_count"),
            "approved_by": approved_by_user_id,
        }
        client.table("memory_promotion_candidates").update(
            {"status": MemoryPromotionStatus.APPROVED.value, "updated_at": self._now().isoformat()}
        ).eq("id", candidate_id).execute()
        return self._promote_candidate(
            client,
            candidate,
            org_id=org_id,
            promotion_path="manual_approval",
            decision_reasoning=reasoning,
            threshold_snapshot=snapshot,
            provenance=provenance_map[candidate_type],
            expires_at=None,
            decided_by=approved_by_user_id,
            status_at_decision=MemoryPromotionStatus.APPROVED.value,
        )

    async def reject_candidate(
        self,
        candidate_id: str,
        org_id: str,
        rejected_by_user_id: str,
        reason: str | None = None,
    ) -> None:
        client = self._client()
        rows = (
            client.table("memory_promotion_candidates")
            .select("*")
            .eq("id", candidate_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            raise ValueError("Promotion candidate not found")
        candidate = rows[0]
        client.table("memory_promotion_candidates").update(
            {
                "status": MemoryPromotionStatus.REJECTED.value,
                "rejection_reason": (reason or "").strip() or None,
                "updated_at": self._now().isoformat(),
            }
        ).eq("id", candidate_id).execute()
        self._record_audit(
            client,
            org_id=org_id,
            memory_id=None,
            candidate_id=candidate_id,
            source_table=str(candidate.get("source_table") or ""),
            source_id=str(candidate.get("source_id")) if candidate.get("source_id") else None,
            promotion_path="manual_approval",
            decision_reasoning=(reason or "Rejected by admin").strip(),
            threshold_snapshot={"candidate_type": candidate.get("candidate_type")},
            status_at_decision=MemoryPromotionStatus.REJECTED.value,
            decided_by=rejected_by_user_id,
            action="reject",
        )

    async def rollback_memory(
        self,
        memory_id: str,
        org_id: str,
        rolled_back_by_user_id: str,
        reason: str,
    ) -> None:
        if not (reason or "").strip():
            raise ValueError("Rollback reason is required")
        client = self._client()
        mem_rows = (
            client.table("agent_memories")
            .select("*")
            .eq("id", memory_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not mem_rows:
            raise ValueError("Memory not found")
        memory = mem_rows[0]
        client.table("agent_memories").update(
            {"is_active": False, "updated_at": self._now().isoformat()}
        ).eq("id", memory_id).execute()

        candidate_rows = (
            client.table("memory_promotion_candidates")
            .select("*")
            .eq("org_id", org_id)
            .contains("memory_ids", json.dumps([memory_id]))
            .limit(1)
            .execute()
            .data
            or []
        )
        candidate = candidate_rows[0] if candidate_rows else None
        if not candidate:
            written = (
                client.table("memory_promotion_candidates")
                .select("*")
                .eq("org_id", org_id)
                .eq("status", MemoryPromotionStatus.WRITTEN.value)
                .execute()
                .data
                or []
            )
            for row in written:
                ids = row.get("memory_ids") or []
                if memory_id in [str(x) for x in ids]:
                    candidate = row
                    break
        if candidate:
            client.table("memory_promotion_candidates").update(
                {
                    "status": MemoryPromotionStatus.ROLLED_BACK.value,
                    "updated_at": self._now().isoformat(),
                }
            ).eq("id", candidate["id"]).execute()
            if candidate.get("source_table") == "org_glossary_terms" and candidate.get("source_id"):
                client.table("org_glossary_terms").update({"status": "candidate"}).eq(
                    "id", candidate["source_id"]
                ).execute()

        self._record_audit(
            client,
            org_id=org_id,
            memory_id=memory_id,
            candidate_id=str(candidate["id"]) if candidate else None,
            source_table=str(memory.get("provenance") or "agent_memories"),
            source_id=None,
            promotion_path="manual_approval",
            decision_reasoning=reason.strip(),
            threshold_snapshot={"rolled_back_memory_id": memory_id},
            status_at_decision=MemoryPromotionStatus.ROLLED_BACK.value,
            decided_by=rolled_back_by_user_id,
            action="rollback",
        )

    async def run_expiration_check(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        now = self._now()
        expired_count = 0
        reset_count = 0

        auto_memories = (
            client.table("agent_memories")
            .select("*")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .like("provenance", f"{V4_PROVENANCE_PREFIX}auto:%")
            .execute()
            .data
            or []
        )
        for memory in auto_memories:
            memory_id = str(memory["id"])
            expires_at_raw = memory.get("expires_at")
            created_at_raw = memory.get("created_at")
            usage_count = int(memory.get("usage_count") or 0)
            last_retrieved = memory.get("last_retrieved_at") or created_at_raw
            should_expire = False

            if expires_at_raw:
                expires_at = datetime.fromisoformat(str(expires_at_raw).replace("Z", "+00:00"))
                if expires_at <= now:
                    term = None
                    prov = str(memory.get("provenance") or "")
                    if "glossary" in prov:
                        content = str(memory.get("content") or "")
                        if "Company term '" in content:
                            term = content.split("Company term '", 1)[1].split("'", 1)[0]
                    if term:
                        term_rows = (
                            client.table("org_glossary_terms")
                            .select("frequency")
                            .eq("org_id", org_id)
                            .eq("term", term)
                            .limit(1)
                            .execute()
                            .data
                            or []
                        )
                        freq = int(term_rows[0]["frequency"]) if term_rows else 0
                        dept_count = self._count_departments_for_term(client, org_id, term)
                        if (
                            freq >= self.AUTO_PROMOTE_MIN_OCCURRENCES
                            and dept_count >= self.AUTO_PROMOTE_MIN_DEPARTMENTS
                        ):
                            new_expires = now + timedelta(days=self.AUTO_PROMOTED_TTL_DAYS)
                            client.table("agent_memories").update(
                                {"expires_at": new_expires.isoformat()}
                            ).eq("id", memory_id).execute()
                            reset_count += 1
                            continue
                    should_expire = True

            if not should_expire and usage_count == 0 and last_retrieved:
                last_dt = datetime.fromisoformat(str(last_retrieved).replace("Z", "+00:00"))
                if last_dt + timedelta(days=self.USAGE_DECAY_DAYS) <= now:
                    should_expire = True

            if should_expire:
                client.table("agent_memories").update({"is_active": False}).eq(
                    "id", memory_id
                ).execute()
                self._record_audit(
                    client,
                    org_id=org_id,
                    memory_id=memory_id,
                    candidate_id=None,
                    source_table="agent_memories",
                    source_id=None,
                    promotion_path="auto",
                    decision_reasoning=(
                        f"Auto-promoted memory expired after TTL/decay policy "
                        f"(usage_count={usage_count}, ttl_days={self.AUTO_PROMOTED_TTL_DAYS}, "
                        f"usage_decay_days={self.USAGE_DECAY_DAYS})."
                    ),
                    threshold_snapshot={
                        "usage_count": usage_count,
                        "auto_promoted_ttl_days": self.AUTO_PROMOTED_TTL_DAYS,
                        "usage_decay_days": self.USAGE_DECAY_DAYS,
                    },
                    status_at_decision=MemoryPromotionStatus.EXPIRED.value,
                    action="expire",
                )
                expired_count += 1

        return {"org_id": org_id, "expired": expired_count, "ttl_reset": reset_count}

    def list_candidates(
        self,
        org_id: str,
        *,
        status: str | None = None,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        client = self._client()
        q = client.table("memory_promotion_candidates").select("*", count="exact").eq("org_id", org_id)
        if status:
            q = q.eq("status", status)
        if source:
            q = q.eq("source_table", source)
        result = q.order("updated_at", desc=True).range(offset, offset + limit - 1).execute()
        items = result.data or []
        enriched = []
        for item in items:
            enriched.append(
                {
                    **item,
                    "thresholdComparison": {
                        "frequency": item.get("frequency"),
                        "departmentCount": item.get("department_count"),
                        "autoPromoteMinOccurrences": self.AUTO_PROMOTE_MIN_OCCURRENCES,
                        "autoPromoteMinDepartments": self.AUTO_PROMOTE_MIN_DEPARTMENTS,
                        "meetsAutoThreshold": (
                            int(item.get("frequency") or 0) >= self.AUTO_PROMOTE_MIN_OCCURRENCES
                            and int(item.get("department_count") or 0)
                            >= self.AUTO_PROMOTE_MIN_DEPARTMENTS
                            and item.get("candidate_type") == "glossary"
                        ),
                        "canAutoPromote": item.get("candidate_type") == "glossary",
                    },
                }
            )
        return {"items": enriched, "total": result.count or len(items), "limit": limit, "offset": offset}

    def list_audit(
        self,
        org_id: str,
        *,
        memory_id: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        client = self._client()
        q = client.table("agent_memory_promotion_audit").select("*", count="exact").eq("org_id", org_id)
        if memory_id:
            q = q.eq("memory_id", memory_id)
        if since:
            q = q.gte("decided_at", since.isoformat())
        result = q.order("decided_at", desc=True).range(offset, offset + limit - 1).execute()
        rows = result.data or []
        return {
            "items": [
                {
                    **row,
                    "decisionReasoning": row.get("decision_reasoning"),
                    "thresholdSnapshot": row.get("threshold_snapshot") or {},
                    "promotionPath": row.get("promotion_path"),
                    "rollbackPath": f"/api/admin/memory-promotion/memories/{row.get('memory_id')}/rollback"
                    if row.get("memory_id")
                    else None,
                }
                for row in rows
            ],
            "total": result.count or len(rows),
            "limit": limit,
            "offset": offset,
        }

    def list_recent_auto_promotions(
        self,
        org_id: str,
        *,
        since_hours: int = 24,
        limit: int = 50,
    ) -> dict[str, Any]:
        since = self._now() - timedelta(hours=since_hours)
        audit = self.list_audit(org_id, since=since, limit=limit, offset=0)
        auto_items = [
            item
            for item in audit["items"]
            if item.get("promotion_path") == "auto" and item.get("action") == "promote"
        ]
        return {
            "items": auto_items,
            "since": since.isoformat(),
            "rollbackEndpoint": "/api/admin/memory-promotion/memories/{memory_id}/rollback",
        }

    def verify_audit_coverage(self, org_id: str) -> dict[str, Any]:
        """Invariant check: every v4 memory has at least one audit row."""
        client = self._client()
        memories = (
            client.table("agent_memories")
            .select("id, provenance")
            .eq("org_id", org_id)
            .like("provenance", f"{V4_PROVENANCE_PREFIX}%")
            .execute()
            .data
            or []
        )
        missing: list[str] = []
        for memory in memories:
            memory_id = str(memory["id"])
            audits = (
                client.table("agent_memory_promotion_audit")
                .select("id")
                .eq("org_id", org_id)
                .eq("memory_id", memory_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if not audits:
                missing.append(memory_id)
        return {
            "v4_memory_count": len(memories),
            "missing_audit_count": len(missing),
            "missing_memory_ids": missing,
            "complete": len(missing) == 0,
        }


_memory_promotion_service: MemoryPromotionService | None = None


def get_memory_promotion_service(settings: Settings | None = None) -> MemoryPromotionService:
    global _memory_promotion_service
    if settings is not None:
        return MemoryPromotionService(settings=settings)
    if _memory_promotion_service is None:
        _memory_promotion_service = MemoryPromotionService()
    return _memory_promotion_service
