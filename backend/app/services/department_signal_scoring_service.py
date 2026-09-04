"""Department signal scoring with explicit source audit and explainable weights."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.intelligence_packs.shared.auth_mode import AuthMode, get_auth_mode, is_activation_allowed
from app.knowledge_fabric.registry import get_spec
from app.services.tool_registry import get_tool_registry
from app.services.tool_service import list_registered_actions

logger = get_logger(__name__)

DepartmentKey = Literal["sales", "marketing", "finance", "hr", "msp"]
SourceStatus = Literal["live_connector", "knowledge_fabric_only", "missing"]

_DEPARTMENT_ORDER: tuple[DepartmentKey, ...] = ("sales", "marketing", "finance", "hr", "msp")
_WORK_OBJECT_TYPE_BY_DEPARTMENT: dict[DepartmentKey, str] = {
    "sales": "opportunity",
    "marketing": "campaign",
    "finance": "financial_issue",
    "hr": "candidate",
    "msp": "vulnerability",
}


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    department: DepartmentKey
    label: str
    connector_vendor: str | None = None
    connector_actions: tuple[str, ...] = ()
    knowledge_source_id: str | None = None
    evidence_vendors: tuple[str, ...] = ()
    note: str | None = None
    saturation: float = 3.0


@dataclass(frozen=True)
class SignalDefinition:
    signal_id: str
    department: DepartmentKey
    label: str
    weight: float
    sources: tuple[str, ...]
    description: str


_SOURCE_DEFS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        source_id="sales.apollo",
        department="sales",
        label="Apollo activity",
        connector_vendor="apollo",
        connector_actions=("apollo.people.search", "apollo.organizations.enrich"),
        saturation=4.0,
    ),
    SourceDefinition(
        source_id="sales.clay",
        department="sales",
        label="Clay enrichment",
        connector_vendor="clay",
        connector_actions=("clay.companies.enrich", "clay.people.enrich"),
        saturation=3.0,
    ),
    SourceDefinition(
        source_id="sales.linkedin",
        department="sales",
        label="LinkedIn signals",
        connector_vendor="linkedin",
        connector_actions=("linkedin.prospect.enrich",),
        saturation=2.0,
        note="Connector exists but signal depth depends on tenant data and scope.",
    ),
    SourceDefinition(
        source_id="sales.hubspot_activity",
        department="sales",
        label="HubSpot CRM engagement",
        connector_vendor="hubspot",
        connector_actions=("hubspot.contacts.list", "hubspot.notes.create"),
        saturation=4.0,
    ),
    SourceDefinition(
        source_id="sales.census_kf",
        department="sales",
        label="Census business-formation context",
        knowledge_source_id="sales.census.api",
        evidence_vendors=("census", "opencorporates", "sec_edgar", "world_bank", "fred"),
        note="Knowledge Fabric source; not a direct tenant connector.",
        saturation=2.0,
    ),
    SourceDefinition(
        source_id="marketing.ga4",
        department="marketing",
        label="Google Analytics 4",
        connector_vendor="google_analytics",
        connector_actions=("google_analytics.reports.run",),
        saturation=4.0,
    ),
    SourceDefinition(
        source_id="marketing.google_ads",
        department="marketing",
        label="Google Ads",
        connector_vendor="google_ads",
        connector_actions=("google_ads.reports.performance", "google_ads.campaigns.list"),
        saturation=4.0,
    ),
    SourceDefinition(
        source_id="marketing.gsc",
        department="marketing",
        label="Google Search Console",
        connector_vendor="google_search_console",
        connector_actions=("google_search_console.searchAnalytics.query",),
        saturation=3.0,
    ),
    SourceDefinition(
        source_id="finance.stripe",
        department="finance",
        label="Stripe payment/invoice history",
        connector_vendor="stripe",
        connector_actions=("stripe.invoices.list", "stripe.customers.get"),
        saturation=4.0,
    ),
    SourceDefinition(
        source_id="finance.quickbooks",
        department="finance",
        label="QuickBooks payment history",
        connector_vendor="quickbooks",
        connector_actions=("quickbooks.invoices.list", "quickbooks.payments.list"),
        saturation=4.0,
    ),
    SourceDefinition(
        source_id="hr.linkedin",
        department="hr",
        label="LinkedIn candidate profile signals",
        connector_vendor="linkedin",
        connector_actions=("linkedin.prospect.enrich",),
        saturation=2.0,
        note="LinkedIn connector is available, but ATS-grade depth still depends on org setup.",
    ),
    SourceDefinition(
        source_id="hr.greenhouse",
        department="hr",
        label="Greenhouse ATS",
        connector_vendor="greenhouse",
        connector_actions=("greenhouse.jobs.list", "greenhouse.candidates.get"),
        saturation=3.0,
    ),
    SourceDefinition(
        source_id="msp.nvd",
        department="msp",
        label="NVD vulnerability feed",
        connector_vendor="nvd",
        connector_actions=("nvd.cve.get",),
        evidence_vendors=("nvd",),
        saturation=2.0,
    ),
    SourceDefinition(
        source_id="msp.cisa_kev",
        department="msp",
        label="CISA KEV feed",
        connector_vendor="cisa_kev",
        connector_actions=("cisa_kev.feed.get",),
        knowledge_source_id="cyber.cisa.advisories",
        evidence_vendors=("cisa_kev",),
        saturation=2.0,
    ),
    SourceDefinition(
        source_id="msp.client_environment",
        department="msp",
        label="Client environment inventory",
        connector_vendor="connectwise",
        connector_actions=("connectwise.companies.list",),
        note="Datto RMM remains a profile preference (partner API); ConnectWise Manage covers PSA inventory.",
        saturation=2.0,
    ),
)

_SIGNAL_DEFS: tuple[SignalDefinition, ...] = (
    SignalDefinition(
        signal_id="sales.hiring_momentum",
        department="sales",
        label="Hiring momentum",
        weight=0.30,
        sources=("sales.linkedin", "sales.apollo"),
        description="Recent hiring-related signal density from prospecting sources.",
    ),
    SignalDefinition(
        signal_id="sales.technology_adoption",
        department="sales",
        label="Technology adoption",
        weight=0.25,
        sources=("sales.clay",),
        description="Tech-stack or enrichment evidence from Clay/Apollo paths.",
    ),
    SignalDefinition(
        signal_id="sales.engagement",
        department="sales",
        label="Engagement signal",
        weight=0.25,
        sources=("sales.hubspot_activity", "sales.apollo"),
        description="CRM or outbound engagement activity tied to opportunities.",
    ),
    SignalDefinition(
        signal_id="sales.firmographic_fit",
        department="sales",
        label="Firmographic fit",
        weight=0.20,
        sources=("sales.census_kf", "sales.apollo"),
        description="Business-formation and company-fit context from Census/KF + Apollo.",
    ),
    SignalDefinition(
        signal_id="marketing.channel_demand",
        department="marketing",
        label="Channel demand",
        weight=0.40,
        sources=("marketing.ga4", "marketing.gsc"),
        description="Inbound demand and content/channel traction.",
    ),
    SignalDefinition(
        signal_id="marketing.paid_efficiency",
        department="marketing",
        label="Paid efficiency",
        weight=0.35,
        sources=("marketing.google_ads", "marketing.ga4"),
        description="Paid channel effort vs observed conversion behavior.",
    ),
    SignalDefinition(
        signal_id="marketing.search_intent",
        department="marketing",
        label="Search intent",
        weight=0.25,
        sources=("marketing.gsc",),
        description="Search Console query/page trend signal strength.",
    ),
    SignalDefinition(
        signal_id="finance.payment_risk",
        department="finance",
        label="Payment risk",
        weight=0.55,
        sources=("finance.stripe", "finance.quickbooks"),
        description="Overdue/payment-latency risk indications.",
    ),
    SignalDefinition(
        signal_id="finance.collections_velocity",
        department="finance",
        label="Collections velocity",
        weight=0.45,
        sources=("finance.stripe", "finance.quickbooks"),
        description="Recent collections and payment confirmation velocity.",
    ),
    SignalDefinition(
        signal_id="hr.req_pressure",
        department="hr",
        label="Hiring pressure",
        weight=0.45,
        sources=("hr.greenhouse", "hr.linkedin"),
        description="Open-role pressure and candidate pipeline signals.",
    ),
    SignalDefinition(
        signal_id="hr.candidate_engagement",
        department="hr",
        label="Candidate engagement",
        weight=0.55,
        sources=("hr.linkedin", "hr.greenhouse"),
        description="Candidate touchpoints and progression activity.",
    ),
    SignalDefinition(
        signal_id="msp.vuln_severity",
        department="msp",
        label="Vulnerability severity",
        weight=0.60,
        sources=("msp.nvd", "msp.cisa_kev"),
        description="CVE/KEV criticality and exploitability pressure.",
    ),
    SignalDefinition(
        signal_id="msp.client_risk_exposure",
        department="msp",
        label="Client risk exposure",
        weight=0.40,
        sources=("msp.client_environment", "msp.nvd", "msp.cisa_kev"),
        description="Known vulnerabilities weighted by client-environment relevance.",
    ),
)

_SOURCE_BY_ID: dict[str, SourceDefinition] = {row.source_id: row for row in _SOURCE_DEFS}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_department(value: str | None) -> DepartmentKey | None:
    text = str(value or "").strip().lower()
    if text in _DEPARTMENT_ORDER:
        return text  # type: ignore[return-value]
    return None


def _priority_band(score_0_100: float) -> str:
    if score_0_100 >= 85:
        return "critical"
    if score_0_100 >= 70:
        return "high"
    if score_0_100 >= 45:
        return "medium"
    return "low"


class DepartmentSignalScoringService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _connected_integrations(self, client: Any, org_id: str) -> set[str]:
        try:
            rows = get_tool_registry().list_connected_integrations(client, org_id)
            return {str(item or "").strip().lower() for item in rows if str(item or "").strip()}
        except Exception as exc:  # noqa: BLE001
            logger.debug("signal_scoring_connected_integrations_failed org_id=%s error=%s", org_id, exc)
            return set()

    @staticmethod
    def _registered_actions() -> set[str]:
        try:
            return {str(item or "").strip().lower() for item in list_registered_actions() if str(item or "").strip()}
        except Exception:  # noqa: BLE001
            return set()

    def _resolve_source_status(
        self,
        source: SourceDefinition,
        *,
        connected: set[str],
        registered_actions: set[str],
    ) -> tuple[SourceStatus, str]:
        kf_spec_exists = bool(source.knowledge_source_id and get_spec(source.knowledge_source_id))
        vendor = str(source.connector_vendor or "").strip().lower()
        if not vendor:
            if kf_spec_exists:
                return "knowledge_fabric_only", "knowledge_source_registered"
            return "missing", "source_not_registered"

        action_live = any(action.lower() in registered_actions for action in source.connector_actions)
        auth_mode = get_auth_mode(vendor)
        if vendor in connected:
            return "live_connector", "connector_connected"
        if auth_mode == AuthMode.GRAVITRE_MANAGED and action_live and is_activation_allowed(vendor, settings=self.settings):
            return "live_connector", "gravitre_managed_source"
        if kf_spec_exists:
            return "knowledge_fabric_only", "knowledge_fabric_fallback"
        if action_live:
            return "missing", "connector_not_connected"
        return "missing", "source_not_implemented"

    def _audit_rows(
        self,
        *,
        org_id: str,
        client: Any,
        departments: set[DepartmentKey] | None = None,
    ) -> list[dict[str, Any]]:
        connected = self._connected_integrations(client, org_id)
        registered_actions = self._registered_actions()
        rows: list[dict[str, Any]] = []
        for source in _SOURCE_DEFS:
            if departments and source.department not in departments:
                continue
            status, reason = self._resolve_source_status(
                source,
                connected=connected,
                registered_actions=registered_actions,
            )
            rows.append(
                {
                    "sourceId": source.source_id,
                    "department": source.department,
                    "label": source.label,
                    "status": status,
                    "statusReason": reason,
                    "connectorVendor": source.connector_vendor,
                    "connectorActions": list(source.connector_actions),
                    "knowledgeSourceId": source.knowledge_source_id,
                    "note": source.note,
                }
            )
        return rows

    def audit_sources(
        self,
        org_id: str,
        *,
        client: Any,
        department: str | None = None,
    ) -> dict[str, Any]:
        dept = _normalize_department(department)
        scoped = {dept} if dept else set(_DEPARTMENT_ORDER)
        rows = self._audit_rows(org_id=org_id, client=client, departments=scoped)
        grouped: list[dict[str, Any]] = []
        for d in _DEPARTMENT_ORDER:
            if d not in scoped:
                continue
            subset = [row for row in rows if row["department"] == d]
            counts = {
                "live_connector": sum(1 for row in subset if row["status"] == "live_connector"),
                "knowledge_fabric_only": sum(1 for row in subset if row["status"] == "knowledge_fabric_only"),
                "missing": sum(1 for row in subset if row["status"] == "missing"),
            }
            grouped.append({"department": d, "sources": subset, "counts": counts})
        return {"capturedAt": _now_iso(), "departments": grouped}

    @staticmethod
    def _load_work_objects(
        client: Any,
        *,
        org_id: str,
        department: DepartmentKey,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = (
            client.table("work_objects")
            .select("id, title, department, object_type, status, priority, metadata, external_entity_id, external_entity_type, last_activity_at")
            .eq("org_id", org_id)
            .eq("department", department)
            .neq("status", "archived")
            .order("last_activity_at", desc=True)
            .limit(max(5, min(limit, 50)))
            .execute()
            .data
            or []
        )
        out = [row for row in rows if isinstance(row, dict)]
        if out:
            return out
        # Department not always persisted on older rows; fallback to object type.
        fallback_type = _WORK_OBJECT_TYPE_BY_DEPARTMENT[department]
        rows = (
            client.table("work_objects")
            .select("id, title, department, object_type, status, priority, metadata, external_entity_id, external_entity_type, last_activity_at")
            .eq("org_id", org_id)
            .eq("object_type", fallback_type)
            .neq("status", "archived")
            .order("last_activity_at", desc=True)
            .limit(max(5, min(limit, 50)))
            .execute()
            .data
            or []
        )
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _load_work_object_events(client: Any, *, org_id: str) -> list[dict[str, Any]]:
        rows = (
            client.table("work_object_events")
            .select("work_object_id, system_name, action_name, created_at")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(1500)
            .execute()
            .data
            or []
        )
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _load_external_signals(client: Any, *, org_id: str) -> list[dict[str, Any]]:
        rows = (
            client.table("external_signals")
            .select("vendor, signal_type, title, detected_at, entity_id, payload")
            .eq("org_id", org_id)
            .order("detected_at", desc=True)
            .limit(1200)
            .execute()
            .data
            or []
        )
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _strength(
        source: SourceDefinition,
        *,
        status: SourceStatus,
        event_hits: int,
        external_hits: int,
    ) -> float:
        if status == "missing":
            return 0.0
        blended = (float(event_hits) * 0.7) + (float(external_hits) * 0.3)
        return round(min(1.0, blended / max(source.saturation, 1.0)), 4)

    def score_department(
        self,
        org_id: str,
        *,
        client: Any,
        department: str,
        limit: int = 5,
        work_object_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        dept = _normalize_department(department)
        if dept is None:
            return {
                "department": department,
                "capturedAt": _now_iso(),
                "priorities": [],
                "gaps": [f"Unsupported department: {department}"],
            }
        source_rows = self._audit_rows(org_id=org_id, client=client, departments={dept})
        source_status = {row["sourceId"]: str(row["status"]) for row in source_rows}
        work_objects = self._load_work_objects(
            client,
            org_id=org_id,
            department=dept,
            limit=max(limit * 4, 12),
        )
        if work_object_ids:
            keep = {str(item) for item in work_object_ids}
            work_objects = [row for row in work_objects if str(row.get("id") or "") in keep]
        if not work_objects:
            return {
                "department": dept,
                "capturedAt": _now_iso(),
                "sourceAudit": source_rows,
                "signalWeights": [
                    {"signalId": spec.signal_id, "label": spec.label, "weight": spec.weight}
                    for spec in _SIGNAL_DEFS
                    if spec.department == dept
                ],
                "priorities": [],
                "gaps": [f"No {dept} WorkObjects with current activity were found."],
            }

        object_ids = {str(row.get("id") or "") for row in work_objects if str(row.get("id") or "")}
        events = [row for row in self._load_work_object_events(client, org_id=org_id) if str(row.get("work_object_id") or "") in object_ids]
        external = self._load_external_signals(client, org_id=org_id)

        signal_specs = [spec for spec in _SIGNAL_DEFS if spec.department == dept]
        department_gaps: list[str] = []
        priorities: list[dict[str, Any]] = []

        for work_object in work_objects[: max(1, min(limit, 20))]:
            wid = str(work_object.get("id") or "")
            object_events = [row for row in events if str(row.get("work_object_id") or "") == wid]
            total_points = 0.0
            weight_used = 0.0
            contributions: list[dict[str, Any]] = []
            local_gaps: list[str] = []

            for signal in signal_specs:
                strengths: list[float] = []
                evidence_rollup: list[dict[str, Any]] = []
                missing_sources: list[str] = []
                for source_id in signal.sources:
                    source = _SOURCE_BY_ID[source_id]
                    status = str(source_status.get(source_id) or "missing")
                    status_typed: SourceStatus = status if status in {"live_connector", "knowledge_fabric_only", "missing"} else "missing"
                    if status_typed == "missing":
                        missing_sources.append(source.label)
                        continue
                    vendors = set(source.evidence_vendors or ())
                    if source.connector_vendor:
                        vendors.add(source.connector_vendor)
                    event_hits = 0
                    if source.connector_vendor:
                        vendor = source.connector_vendor.lower()
                        event_hits = sum(
                            1
                            for row in object_events
                            if str(row.get("system_name") or "").strip().lower() == vendor
                        )
                    external_hits = 0
                    if vendors:
                        external_hits = sum(
                            1
                            for row in external
                            if str(row.get("vendor") or "").strip().lower() in vendors
                        )
                    strength = self._strength(
                        source,
                        status=status_typed,
                        event_hits=event_hits,
                        external_hits=external_hits,
                    )
                    strengths.append(strength)
                    evidence_rollup.append(
                        {
                            "sourceId": source.source_id,
                            "sourceLabel": source.label,
                            "status": status_typed,
                            "eventHits": event_hits,
                            "externalSignalHits": external_hits,
                            "strength": strength,
                        }
                    )
                    if event_hits + external_hits == 0:
                        local_gaps.append(
                            f"{signal.label}: no recent evidence from {source.label}."
                        )

                if not strengths:
                    local_gaps.append(f"{signal.label}: no live source available.")
                    if missing_sources:
                        department_gaps.append(
                            f"{signal.label}: missing source(s) {', '.join(missing_sources)}."
                        )
                    continue

                component_score = round(sum(strengths) / max(len(strengths), 1), 4)
                points = round(component_score * signal.weight * 100.0, 2)
                total_points += points
                weight_used += signal.weight
                contributions.append(
                    {
                        "signalId": signal.signal_id,
                        "label": signal.label,
                        "weight": signal.weight,
                        "signalScore": component_score,
                        "points": points,
                        "description": signal.description,
                        "evidence": evidence_rollup,
                    }
                )

            if weight_used <= 0:
                score_100 = 0.0
            else:
                score_100 = round(total_points / weight_used, 2)
            explanations = [
                (
                    f"{item['label']} +{item['points']:.1f} pts "
                    f"(signal={item['signalScore']:.2f}, weight={item['weight']:.2f})"
                )
                for item in sorted(contributions, key=lambda row: float(row.get("points") or 0.0), reverse=True)
                if float(item.get("points") or 0.0) > 0
            ]
            priorities.append(
                {
                    "workObjectId": wid,
                    "title": str(work_object.get("title") or f"{dept.title()} priority"),
                    "department": dept,
                    "objectType": str(work_object.get("object_type") or ""),
                    "status": str(work_object.get("status") or ""),
                    "externalEntityId": str(work_object.get("external_entity_id") or "") or None,
                    "priorityScore": score_100,
                    "priorityBand": _priority_band(score_100),
                    "signalContributions": contributions,
                    "explanations": explanations[:4],
                    "gaps": sorted(set(local_gaps))[:8],
                }
            )

        priorities.sort(key=lambda row: float(row.get("priorityScore") or 0.0), reverse=True)
        return {
            "department": dept,
            "capturedAt": _now_iso(),
            "sourceAudit": source_rows,
            "signalWeights": [
                {"signalId": spec.signal_id, "label": spec.label, "weight": spec.weight}
                for spec in signal_specs
            ],
            "priorities": priorities[: max(1, min(limit, 20))],
            "gaps": sorted(set(department_gaps))[:12],
        }

    def score_all_departments(
        self,
        org_id: str,
        *,
        client: Any,
        limit_per_department: int = 3,
    ) -> dict[str, Any]:
        return {
            "capturedAt": _now_iso(),
            "departments": [
                self.score_department(
                    org_id,
                    client=client,
                    department=dept,
                    limit=limit_per_department,
                )
                for dept in _DEPARTMENT_ORDER
            ],
        }

    @staticmethod
    def render_priority_context(score_payload: dict[str, Any]) -> str:
        dept = str(score_payload.get("department") or "")
        priorities = list(score_payload.get("priorities") or [])
        if not priorities:
            gaps = list(score_payload.get("gaps") or [])
            gap_text = "; ".join(str(item) for item in gaps[:3]) or "No scored priorities available."
            return f"SIGNAL PRIORITIZATION ({dept or 'unknown'}): {gap_text}"
        lines = [f"SIGNAL PRIORITIZATION ({dept}):"]
        for row in priorities[:3]:
            lines.append(
                f"- {row.get('title')} — score {row.get('priorityScore')}/100 ({row.get('priorityBand')})"
            )
            for reason in list(row.get("explanations") or [])[:2]:
                lines.append(f"  • {reason}")
        gaps = list(score_payload.get("gaps") or [])
        if gaps:
            lines.append(f"Known gaps: {'; '.join(str(item) for item in gaps[:2])}")
        return "\n".join(lines)


_service: DepartmentSignalScoringService | None = None


def get_department_signal_scoring_service(settings: Settings | None = None) -> DepartmentSignalScoringService:
    global _service
    if _service is None or settings is not None:
        _service = DepartmentSignalScoringService(settings)
    return _service
