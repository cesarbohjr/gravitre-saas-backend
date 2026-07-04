"""Domain-aware retrieval policy — weighting layer only, not a retrieval engine."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.config import Settings, get_settings
from app.domain.loader import load_domain_profile
from app.services.domain_intelligence_service import DOMAIN_CONFIDENCE_THRESHOLD

POLICY_VERSION = "domain_v1"

_GRAPH_ELEVATED_DEPARTMENTS = frozenset({"sales", "support", "msp", "operations"})
_GRAPH_ELEVATED_SUBDOMAINS = frozenset(
    {
        "pipeline_management",
        "forecasting",
        "revenue_operations",
        "technical_support",
        "escalations",
        "customer_success",
        "noc",
        "rmm",
        "helpdesk",
        "process_improvement",
        "business_operations",
    }
)


@dataclass
class RetrievalPlan:
    """Central retrieval weighting plan — future learning systems adjust deltas only."""

    active: bool = False
    policy_version: str = POLICY_VERSION
    source_type_weights: dict[str, float] = field(default_factory=dict)
    assignment_boosts: dict[str, float] = field(default_factory=dict)
    memory_category_boosts: list[str] = field(default_factory=list)
    retrieval_tag_boosts: list[str] = field(default_factory=list)
    connector_priorities: list[str] = field(default_factory=list)
    deprioritize_departments: list[str] = field(default_factory=list)
    graph_weight: float = 0.0
    require_assigned_only: bool = False
    strict_assignment_mode: bool = False
    allow_label_fallback: bool = True
    allow_unassigned_with_lower_confidence: bool = True
    provenance_required: bool = True
    domain_department: str | None = None
    domain_subdomain: str | None = None
    profile_id: str | None = None
    adaptive_weight_delta: float = 0.0
    meta_learning_delta: float = 0.0
    freshness_multiplier: float = 1.0
    outcome_multiplier: float = 1.0
    optimization_multiplier: float = 1.0

    def to_params(self) -> dict[str, Any]:
        return asdict(self)

    def learning_multiplier(self) -> float:
        base = 1.0 + float(self.adaptive_weight_delta or 0) + float(self.meta_learning_delta or 0)
        return base * float(self.freshness_multiplier or 1.0) * float(self.outcome_multiplier or 1.0) * float(
            self.optimization_multiplier or 1.0
        )


def is_domain_retrieval_enabled(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    return bool(getattr(cfg, "domain_retrieval_policy_enabled", False))


def build_retrieval_plan(
    classification: dict[str, Any] | None,
    assignments: list[dict[str, Any]] | None = None,
    *,
    settings: Settings | None = None,
    strict_assignment_mode: bool | None = None,
) -> RetrievalPlan:
    cfg = settings or get_settings()
    if not is_domain_retrieval_enabled(cfg):
        return RetrievalPlan(active=False)

    domain = (classification or {}).get("domain") or {}
    routing_active = domain.get("routing_active")
    if routing_active is False:
        return RetrievalPlan(active=False)
    confidence = float(domain.get("confidence") or 0)
    if routing_active is not True and confidence < DOMAIN_CONFIDENCE_THRESHOLD:
        return RetrievalPlan(active=False)

    dept_key = str(domain.get("department_key") or domain.get("department") or "").lower()
    sub_key = str(domain.get("subdomain_key") or domain.get("subdomain") or "").lower()
    profile_id = domain.get("profile_id") or dept_key or None
    profile = load_domain_profile(str(profile_id)) if profile_id else None

    retrieval_tags = [str(t).lower() for t in (profile or {}).get("retrieval_preferences") or []]
    memory_priorities = [str(t).lower() for t in (profile or {}).get("memory_priorities") or []]
    connector_prefs = [str(c).lower() for c in (profile or {}).get("connector_preferences") or []]

    source_weights = {
        "rag": 0.85,
        "agent_memory": 0.78,
        "graph": 0.88,
        "org_context": 0.72,
        "hybrid_memory": 0.75,
        "company_intelligence": 0.65,
        "connector_context": 0.68,
    }

    graph_weight = _resolve_graph_weight(classification or {}, dept_key, sub_key)
    source_weights["graph"] = graph_weight

    if retrieval_tags:
        source_weights["rag"] = min(1.2, source_weights["rag"] + 0.12)
    if memory_priorities:
        source_weights["agent_memory"] = min(1.15, source_weights["agent_memory"] + 0.1)

    if dept_key in {"marketing"} and sub_key in {"seo", "content_marketing", "analytics"}:
        source_weights["graph"] = min(source_weights["graph"], 0.35)

    deprioritize = _deprioritized_departments(dept_key)
    assignment_boosts = _assignment_boosts(assignments or [], dept_key, sub_key, connector_prefs)

    strict = bool(strict_assignment_mode) if strict_assignment_mode is not None else False

    return RetrievalPlan(
        active=True,
        source_type_weights=source_weights,
        assignment_boosts=assignment_boosts,
        memory_category_boosts=memory_priorities,
        retrieval_tag_boosts=retrieval_tags,
        connector_priorities=connector_prefs,
        deprioritize_departments=deprioritize,
        graph_weight=graph_weight,
        require_assigned_only=strict,
        strict_assignment_mode=strict,
        allow_label_fallback=confidence < DOMAIN_CONFIDENCE_THRESHOLD or not strict,
        allow_unassigned_with_lower_confidence=not strict,
        provenance_required=True,
        domain_department=dept_key or None,
        domain_subdomain=sub_key or None,
        profile_id=str(profile_id) if profile_id else None,
    )


def should_fetch_graph(classification: dict[str, Any] | None, plan: RetrievalPlan) -> bool:
    if not plan.active:
        return bool((classification or {}).get("requires_graph"))
    if bool((classification or {}).get("requires_graph")):
        return True
    return float(plan.graph_weight or 0) >= 0.7


def _resolve_graph_weight(classification: dict[str, Any], dept_key: str, sub_key: str) -> float:
    if bool(classification.get("requires_graph")):
        return 0.88
    if dept_key in _GRAPH_ELEVATED_DEPARTMENTS or sub_key in _GRAPH_ELEVATED_SUBDOMAINS:
        if dept_key == "sales" or sub_key in {"pipeline_management", "forecasting", "revenue_operations"}:
            return 0.95
        if dept_key == "support" or sub_key in {"technical_support", "escalations", "customer_success"}:
            return 0.92
        if dept_key == "msp" or sub_key in {"noc", "rmm", "helpdesk"}:
            return 0.90
        if dept_key == "operations":
            return 0.85
    return 0.45


def _deprioritized_departments(active_department: str) -> list[str]:
    if not active_department:
        return []
    all_depts = {
        "marketing",
        "sales",
        "finance",
        "hr",
        "support",
        "operations",
        "engineering",
        "msp",
    }
    return sorted(all_depts - {active_department})


def _assignment_boosts(
    assignments: list[dict[str, Any]],
    dept_key: str,
    sub_key: str,
    connector_prefs: list[str],
) -> dict[str, float]:
    boosts: dict[str, float] = {}
    for row in assignments:
        if not row.get("enabled", True):
            continue
        assignment_id = str(row.get("id") or "")
        if not assignment_id:
            continue
        weight = float(row.get("confidenceWeight") or row.get("confidence_weight") or 1.0)
        row_dept = str(row.get("department") or row.get("owningDepartment") or row.get("owning_department") or "").lower()
        row_sub = str(row.get("subdomain") or "").lower()
        source_type = str(row.get("sourceType") or row.get("source_type") or "").lower()
        if dept_key and row_dept == dept_key:
            weight *= 1.2
        if sub_key and row_sub == sub_key:
            weight *= 1.3
        if connector_prefs and any(pref in source_type for pref in connector_prefs):
            weight *= 1.1
        boosts[assignment_id] = round(min(2.0, max(0.5, weight)), 4)
    return boosts


def apply_source_score(
    base_score: float,
    source: dict[str, Any],
    plan: RetrievalPlan,
    *,
    match_tier: str | None = None,
) -> float:
    if not plan.active:
        return base_score
    score = float(base_score or 0.0)
    meta = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
    assignment_id = str(meta.get("assignment_id") or meta.get("assignmentId") or source.get("assignment_id") or "")
    if assignment_id and assignment_id in plan.assignment_boosts:
        score *= plan.assignment_boosts[assignment_id]
    source_dept = str(meta.get("department") or "").lower()
    if plan.domain_department and source_dept and source_dept in plan.deprioritize_departments:
        score *= 0.4
    if match_tier == "unassigned":
        score *= 0.65
    elif match_tier == "label_fallback":
        score *= 0.75
    elif match_tier == "department_subdomain":
        score *= 0.9
    score *= plan.learning_multiplier()
    return round(score, 6)
