"""Knowledge freshness — stale/inaccessible source assessment for retrieval and trust."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.services.agent_knowledge_assignment_service import FRESHNESS_STALE_HOURS

FRESHNESS_MULTIPLIER_FRESH = 1.0
FRESHNESS_MULTIPLIER_STALE = 0.85
FRESHNESS_MULTIPLIER_EXPIRED = 0.6
FRESHNESS_MULTIPLIER_UNKNOWN = 0.75
FRESHNESS_MULTIPLIER_INACCESSIBLE = 0.0


@dataclass(frozen=True)
class FreshnessAssessment:
    assignment_id: str
    freshness_score: float
    freshness_multiplier: float
    stale: bool
    stale_reason: str | None
    source_accessible: bool
    permission_valid: bool
    sync_status: str
    trust_warning: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "freshness_score": round(float(self.freshness_score), 4),
            "freshness_multiplier": round(float(self.freshness_multiplier), 4),
            "stale": self.stale,
            "stale_reason": self.stale_reason,
            "source_accessible": self.source_accessible,
            "permission_valid": self.permission_valid,
            "sync_status": self.sync_status,
            "trust_warning": self.trust_warning,
        }


class KnowledgeFreshnessService:
    """Assess knowledge source freshness without deleting historical learning data."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def assess_assignment(
        self,
        assignment: dict[str, Any],
        *,
        client: Any | None = None,
        org_id: str | None = None,
    ) -> FreshnessAssessment:
        assignment_id = str(assignment.get("id") or "")
        label = str(assignment.get("label") or assignment.get("sourceType") or "source")
        metadata = assignment.get("metadata") if isinstance(assignment.get("metadata"), dict) else {}

        permission_valid = self._permission_valid(assignment, metadata)
        source_accessible = self._source_accessible(assignment, metadata)
        sync_status = str(
            assignment.get("sync_status")
            or assignment.get("syncStatus")
            or metadata.get("sync_status")
            or "unknown"
        ).lower()

        if not permission_valid:
            return self._inaccessible(
                assignment_id,
                stale_reason="permission_denied",
                label=label,
                sync_status=sync_status,
            )
        if not source_accessible or sync_status in {"failed", "error", "revoked", "deleted"}:
            return self._inaccessible(
                assignment_id,
                stale_reason="source_inaccessible",
                label=label,
                sync_status=sync_status,
            )

        freshness_status = str(
            assignment.get("freshnessStatus") or assignment.get("freshness_status") or ""
        ).lower()
        if not freshness_status and client and org_id:
            from app.services.agent_knowledge_assignment_service import get_agent_knowledge_assignment_service

            freshness_status = get_agent_knowledge_assignment_service(self.settings)._compute_freshness(
                client,
                org_id,
                assignment,
            )

        last_synced = assignment.get("lastSyncedAt") or assignment.get("last_synced_at")
        last_verified = assignment.get("lastVerifiedAt") or assignment.get("last_verified_at")
        reference_score = assignment.get("freshnessScore") or assignment.get("freshness_score")

        if freshness_status == "fresh":
            score = float(reference_score or 0.9)
            return FreshnessAssessment(
                assignment_id=assignment_id,
                freshness_score=score,
                freshness_multiplier=FRESHNESS_MULTIPLIER_FRESH,
                stale=False,
                stale_reason=None,
                source_accessible=True,
                permission_valid=True,
                sync_status=sync_status,
                trust_warning=None,
            )
        if freshness_status == "stale":
            return FreshnessAssessment(
                assignment_id=assignment_id,
                freshness_score=float(reference_score or 0.65),
                freshness_multiplier=FRESHNESS_MULTIPLIER_STALE,
                stale=True,
                stale_reason="stale_sync",
                source_accessible=True,
                permission_valid=True,
                sync_status=sync_status,
                trust_warning=f"Knowledge source '{label}' is stale — refresh or revalidate recommended.",
            )
        if freshness_status == "expired":
            return FreshnessAssessment(
                assignment_id=assignment_id,
                freshness_score=float(reference_score or 0.35),
                freshness_multiplier=FRESHNESS_MULTIPLIER_EXPIRED,
                stale=True,
                stale_reason="expired_sync",
                source_accessible=True,
                permission_valid=True,
                sync_status=sync_status,
                trust_warning=f"Knowledge source '{label}' is expired — confidence reduced until refreshed.",
            )

        age_hours = self._age_hours(last_synced or last_verified)
        if age_hours is not None:
            if age_hours <= FRESHNESS_STALE_HOURS:
                return FreshnessAssessment(
                    assignment_id=assignment_id,
                    freshness_score=0.88,
                    freshness_multiplier=FRESHNESS_MULTIPLIER_FRESH,
                    stale=False,
                    stale_reason=None,
                    source_accessible=True,
                    permission_valid=True,
                    sync_status=sync_status,
                    trust_warning=None,
                )
            if age_hours <= FRESHNESS_STALE_HOURS * 3:
                return FreshnessAssessment(
                    assignment_id=assignment_id,
                    freshness_score=0.62,
                    freshness_multiplier=FRESHNESS_MULTIPLIER_STALE,
                    stale=True,
                    stale_reason="stale_sync",
                    source_accessible=True,
                    permission_valid=True,
                    sync_status=sync_status,
                    trust_warning=f"Knowledge source '{label}' has not synced recently.",
                )
            return FreshnessAssessment(
                assignment_id=assignment_id,
                freshness_score=0.3,
                freshness_multiplier=FRESHNESS_MULTIPLIER_EXPIRED,
                stale=True,
                stale_reason="expired_sync",
                source_accessible=True,
                permission_valid=True,
                sync_status=sync_status,
                trust_warning=f"Knowledge source '{label}' is outdated — revalidation required.",
            )

        return FreshnessAssessment(
            assignment_id=assignment_id,
            freshness_score=float(reference_score or 0.4),
            freshness_multiplier=FRESHNESS_MULTIPLIER_UNKNOWN,
            stale=True,
            stale_reason="unknown_freshness",
            source_accessible=True,
            permission_valid=True,
            sync_status=sync_status,
            trust_warning=f"Knowledge source '{label}' freshness is unknown — verify before relying on it.",
        )

    def assess_assignments(
        self,
        assignments: list[dict[str, Any]],
        *,
        client: Any | None = None,
        org_id: str | None = None,
    ) -> dict[str, FreshnessAssessment]:
        results: dict[str, FreshnessAssessment] = {}
        for row in assignments:
            if not row.get("enabled", True):
                continue
            assignment_id = str(row.get("id") or "")
            if not assignment_id:
                continue
            results[assignment_id] = self.assess_assignment(row, client=client, org_id=org_id)
        return results

    def aggregate_freshness_label(self, assessments: dict[str, FreshnessAssessment]) -> str:
        if not assessments:
            return "unknown"
        multipliers = [item.freshness_multiplier for item in assessments.values()]
        if any(value == FRESHNESS_MULTIPLIER_INACCESSIBLE for value in multipliers):
            return "inaccessible_sources_present"
        if any(item.stale for item in assessments.values()):
            return "stale_sources_present"
        if all(value >= FRESHNESS_MULTIPLIER_FRESH for value in multipliers):
            return "fresh"
        return "mixed"

    def collect_trust_warnings(self, assessments: dict[str, FreshnessAssessment]) -> list[str]:
        warnings: list[str] = []
        seen: set[str] = set()
        for item in assessments.values():
            if item.trust_warning and item.trust_warning not in seen:
                warnings.append(item.trust_warning)
                seen.add(item.trust_warning)
        return warnings

    def confidence_penalty(self, assessments: dict[str, FreshnessAssessment]) -> float:
        if not assessments:
            return 0.0
        stale_count = sum(1 for item in assessments.values() if item.stale)
        inaccessible_count = sum(
            1 for item in assessments.values() if item.freshness_multiplier == FRESHNESS_MULTIPLIER_INACCESSIBLE
        )
        if inaccessible_count:
            return min(0.25, 0.05 * inaccessible_count)
        if stale_count:
            return min(0.15, 0.03 * stale_count)
        return 0.0

    async def load_admin_summary(self, org_id: str, *, client: Any | None = None) -> dict[str, Any]:
        from app.workflows.repository import get_supabase_client

        db = client or get_supabase_client(self.settings)
        try:
            rows = (
                db.table("agent_knowledge_assignments")
                .select(
                    "id, org_id, agent_id, source_type, source_id, label, department, subdomain, "
                    "freshness_status, last_synced_at, last_verified_at, confidence_weight, enabled, metadata"
                )
                .eq("org_id", org_id)
                .eq("enabled", True)
                .order("updated_at", desc=True)
                .limit(500)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            rows = []

        stale_sources: list[dict[str, Any]] = []
        inaccessible_sources: list[dict[str, Any]] = []
        freshness_scores: list[dict[str, Any]] = []
        affected_agents: dict[str, dict[str, Any]] = {}
        affected_domains: dict[str, dict[str, Any]] = {}
        recommended_actions: list[dict[str, Any]] = []
        assessments: dict[str, FreshnessAssessment] = {}

        for row in rows:
            assessment = self.assess_assignment(row, client=db, org_id=org_id)
            assessments[assessment.assignment_id] = assessment
            agent_id = str(row.get("agent_id") or "")
            department = str(row.get("department") or row.get("owning_department") or "").lower()
            subdomain = str(row.get("subdomain") or "").lower()
            entry = {
                "assignment_id": assessment.assignment_id,
                "label": row.get("label"),
                "agent_id": agent_id,
                "source_type": row.get("source_type"),
                "source_id": row.get("source_id"),
                "department": department or None,
                "subdomain": subdomain or None,
                **assessment.to_dict(),
            }
            freshness_scores.append(entry)
            if agent_id:
                affected_agents.setdefault(
                    agent_id,
                    {"agent_id": agent_id, "assignment_count": 0, "stale_count": 0, "inaccessible_count": 0},
                )
                affected_agents[agent_id]["assignment_count"] += 1
            domain_key = f"{department}:{subdomain}" if department or subdomain else "unknown"
            affected_domains.setdefault(
                domain_key,
                {
                    "department": department or None,
                    "subdomain": subdomain or None,
                    "assignment_count": 0,
                    "stale_count": 0,
                    "inaccessible_count": 0,
                },
            )
            affected_domains[domain_key]["assignment_count"] += 1

            if assessment.freshness_multiplier == FRESHNESS_MULTIPLIER_INACCESSIBLE:
                inaccessible_sources.append(entry)
                if agent_id:
                    affected_agents[agent_id]["inaccessible_count"] += 1
                affected_domains[domain_key]["inaccessible_count"] += 1
                recommended_actions.append(
                    {
                        "action": "revalidate_permissions",
                        "assignment_id": assessment.assignment_id,
                        "label": row.get("label"),
                        "reason": assessment.stale_reason or "source_inaccessible",
                    }
                )
            elif assessment.stale:
                stale_sources.append(entry)
                if agent_id:
                    affected_agents[agent_id]["stale_count"] += 1
                affected_domains[domain_key]["stale_count"] += 1
                recommended_actions.append(
                    {
                        "action": "refresh_knowledge_source",
                        "assignment_id": assessment.assignment_id,
                        "label": row.get("label"),
                        "reason": assessment.stale_reason or "stale_sync",
                    }
                )

        return {
            "status": "ok",
            "org_id": org_id,
            "assignment_count": len(rows),
            "stale_sources": stale_sources,
            "inaccessible_sources": inaccessible_sources,
            "freshness_scores": freshness_scores,
            "affected_agents": list(affected_agents.values()),
            "affected_domains": list(affected_domains.values()),
            "recommended_actions": recommended_actions,
            "freshness_label": self.aggregate_freshness_label(assessments) if assessments else "unknown",
            "last_assessed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _inaccessible(
        self,
        assignment_id: str,
        *,
        stale_reason: str,
        label: str,
        sync_status: str,
    ) -> FreshnessAssessment:
        return FreshnessAssessment(
            assignment_id=assignment_id,
            freshness_score=0.0,
            freshness_multiplier=FRESHNESS_MULTIPLIER_INACCESSIBLE,
            stale=True,
            stale_reason=stale_reason,
            source_accessible=False,
            permission_valid=stale_reason != "permission_denied",
            sync_status=sync_status,
            trust_warning=f"Knowledge source '{label}' is inaccessible — excluded from retrieval.",
        )

    @staticmethod
    def _permission_valid(assignment: dict[str, Any], metadata: dict[str, Any]) -> bool:
        if assignment.get("permission_valid") is False or metadata.get("permission_valid") is False:
            return False
        permission_scope = assignment.get("permissionScope") or assignment.get("permission_scope") or {}
        if isinstance(permission_scope, dict) and permission_scope.get("valid") is False:
            return False
        policy = assignment.get("permissionPolicy") or assignment.get("permission_policy") or {}
        if isinstance(policy, dict) and policy.get("denied") is True:
            return False
        return True

    @staticmethod
    def _source_accessible(assignment: dict[str, Any], metadata: dict[str, Any]) -> bool:
        if assignment.get("source_accessible") is False or metadata.get("source_accessible") is False:
            return False
        if metadata.get("deleted") is True or metadata.get("renamed") is True:
            return False
        return True

    @staticmethod
    def _age_hours(timestamp: Any) -> float | None:
        if not timestamp:
            return None
        try:
            synced_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - synced_at).total_seconds() / 3600
        except Exception:  # noqa: BLE001
            return None


_service: KnowledgeFreshnessService | None = None


def get_knowledge_freshness_service(settings: Settings | None = None) -> KnowledgeFreshnessService:
    global _service
    if _service is None or settings is not None:
        _service = KnowledgeFreshnessService(settings)
    return _service
