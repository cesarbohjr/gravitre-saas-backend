"""Capability registry — one read-only view over the canonical runtime.

Every answer here is derived from an existing source of truth; nothing is
declared locally except the evidence-state vocabulary, which maps onto
existing stores. Plays consume this registry instead of keeping their own
catalog of connectors, actions, events or metrics.

Static answers (catalog, step types, event taxonomy, verification modes) need
no org. Org answers (connected vendors, agents, metric overrides) always take
an explicit ``org_id`` and filter by it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Iterable, Literal

from app.connectors.action_catalog.models import ActionSpec, VendorCatalogSpec
from app.connectors.action_catalog.registry import get_vendor_catalog
from app.connectors.action_catalog.tool_aliases import catalog_tool_is_implemented
from app.connectors.constants import is_connector_usable
from app.services.catalog_write_authority import catalog_action_requires_write_approval
from app.services.write_success_verification import resolve_success_verification
from app.workflows.constants import ALLOWED_STEP_TYPES, EXECUTE_ALLOWED_STEP_TYPES

Readiness = Literal["AVAILABLE", "PARTIAL", "MISSING", "EXTERNAL_CONNECTION_REQUIRED"]
EvidenceState = Literal["SIGNAL", "CONTEXT", "RECOMMENDATION", "ACTION", "VERIFICATION", "OUTCOME"]

EVIDENCE_STATES: tuple[EvidenceState, ...] = (
    "SIGNAL",
    "CONTEXT",
    "RECOMMENDATION",
    "ACTION",
    "VERIFICATION",
    "OUTCOME",
)


@dataclass(frozen=True)
class ActionCapability:
    tool: str
    vendor: str
    name: str
    tier: str
    kind: str
    access: Literal["read", "write"]
    requires_approval: bool
    destructive: bool
    implemented: bool
    verification_mode: str | None
    compensating_action: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConnectorCapability:
    vendor: str
    display_name: str
    category: str
    shipped: bool
    action_count: int
    implemented_read_count: int
    implemented_write_count: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tool_key(vendor: str, action: ActionSpec) -> str:
    if action.id.startswith(f"{vendor}."):
        return action.id
    return f"{vendor}.{action.id}"


def _implemented_tools() -> set[str]:
    from app.services.tool_service import list_registered_actions

    return set(list_registered_actions())


def _action_capability(
    vendor_spec: VendorCatalogSpec, action: ActionSpec, implemented: set[str]
) -> ActionCapability:
    tool = _tool_key(vendor_spec.vendor, action)
    writes = catalog_action_requires_write_approval(
        kind=action.kind,
        destructive=action.destructive,
        requires_approval=action.requires_approval,
        scopes=action.scopes,
    )
    return ActionCapability(
        tool=tool,
        vendor=vendor_spec.vendor,
        name=action.name,
        tier=action.tier,
        kind=action.kind,
        access="write" if writes else "read",
        requires_approval=writes,
        destructive=bool(action.destructive),
        implemented=catalog_tool_is_implemented(tool, implemented),
        verification_mode=resolve_success_verification(tool).mode if writes else None,
        compensating_action=action.compensating_action,
    )


@lru_cache(maxsize=1)
def _action_index() -> dict[str, ActionCapability]:
    implemented = _implemented_tools()
    index: dict[str, ActionCapability] = {}
    for vendor_spec in get_vendor_catalog().values():
        for action in vendor_spec.all_actions():
            cap = _action_capability(vendor_spec, action, implemented)
            index[cap.tool.lower()] = cap
    return index


def clear_registry_cache() -> None:
    _action_index.cache_clear()


def list_actions(
    *,
    vendor: str | None = None,
    access: Literal["read", "write"] | None = None,
    implemented_only: bool = False,
) -> list[ActionCapability]:
    wanted_vendor = vendor.strip().lower() if vendor else None
    out = []
    for cap in _action_index().values():
        if wanted_vendor and cap.vendor != wanted_vendor:
            continue
        if access and cap.access != access:
            continue
        if implemented_only and not cap.implemented:
            continue
        out.append(cap)
    return sorted(out, key=lambda c: c.tool)


def get_action(tool: str) -> ActionCapability | None:
    return _action_index().get(str(tool or "").strip().lower())


def approval_required_actions(*, implemented_only: bool = True) -> list[ActionCapability]:
    return [c for c in list_actions(implemented_only=implemented_only) if c.requires_approval]


def list_catalog_connectors() -> list[ConnectorCapability]:
    by_vendor: dict[str, list[ActionCapability]] = {}
    for cap in _action_index().values():
        by_vendor.setdefault(cap.vendor, []).append(cap)
    out = []
    for vendor, spec in get_vendor_catalog().items():
        caps = by_vendor.get(vendor, [])
        out.append(
            ConnectorCapability(
                vendor=vendor,
                display_name=spec.display_name,
                category=spec.category,
                shipped=bool(spec.shipped),
                action_count=len(caps),
                implemented_read_count=sum(1 for c in caps if c.implemented and c.access == "read"),
                implemented_write_count=sum(1 for c in caps if c.implemented and c.access == "write"),
            )
        )
    return sorted(out, key=lambda c: c.vendor)


def workflow_primitives() -> list[dict[str, Any]]:
    return [
        {"step_type": step, "execute_allowed": step in EXECUTE_ALLOWED_STEP_TYPES}
        for step in sorted(ALLOWED_STEP_TYPES)
    ]


def event_taxonomy() -> dict[str, list[str]]:
    from app.services.execution_outcome import TERMINAL_STATUSES
    from app.services.intelligence_outcome_path import (
        ACTION_EVENTS,
        OUTCOME_RESULT_EVENTS,
        SIGNAL_EVENTS,
    )
    from app.services.notification_emitter import CANONICAL_EVENT_TYPES
    from app.services.outcome_learning_service import (
        BUSINESS_IMPACT_EVENTS,
        OUTCOME_EVENTS,
        TOOL_SUCCESS_EVENTS,
    )

    return {
        "signal_events": sorted(SIGNAL_EVENTS),
        "action_events": sorted(ACTION_EVENTS),
        "outcome_result_events": sorted(OUTCOME_RESULT_EVENTS),
        "learning_events": sorted(OUTCOME_EVENTS),
        "execution_evidence_events": sorted(TOOL_SUCCESS_EVENTS),
        "business_impact_events": sorted(BUSINESS_IMPACT_EVENTS),
        "notification_events": sorted(CANONICAL_EVENT_TYPES),
        "run_terminal_statuses": sorted(TERMINAL_STATUSES),
    }


def verification_mechanisms() -> dict[str, Any]:
    by_mode: dict[str, int] = {}
    unverified_implemented: list[str] = []
    for cap in list_actions(access="write"):
        mode = cap.verification_mode or "none"
        by_mode[mode] = by_mode.get(mode, 0) + 1
        if cap.implemented and mode == "accepted_async":
            unverified_implemented.append(cap.tool)
    return {
        "write_verification_modes": by_mode,
        "implemented_writes_accepted_async_only": sorted(unverified_implemented),
        "run_outcome_verification": ["verified", "accepted_unproven", "unverified"],
    }


def evidence_sources() -> dict[EvidenceState, list[str]]:
    """Where each evidence state already lives. States are never merged into one "success"."""
    return {
        "SIGNAL": ["intelligence_outcome_events (signal_events)", "connector read results"],
        "CONTEXT": ["cognitive_turn_traces", "rag_* / org_knowledge_nodes", "conversations.task_state"],
        "RECOMMENDATION": ["intelligence_outcome_events (recommendation_created)", "recommendations"],
        "ACTION": ["audit_events (tool.invoke.* / workflow.execute.*)", "workflow_steps"],
        "VERIFICATION": ["write_success_verification", "workflow_runs.verified_output"],
        "OUTCOME": ["intelligence_outcome_events (outcome_result_events)", "agent_action_outcomes"],
    }


def business_metrics(client: Any = None, org_id: str | None = None) -> dict[str, Any]:
    from app.services.cognitive_metrics import list_metrics_with_defaults, list_platform_defaults

    if client is None or not org_id:
        return {"defaults": list_platform_defaults(), "overrides": [], "orgId": None}
    return list_metrics_with_defaults(client, org_id)


def connected_vendors(client: Any, org_id: str, environment_name: str = "production") -> set[str]:
    from app.connectors.repository import list_connectors as list_org_connectors

    vendors: set[str] = set()
    for row in list_org_connectors(client, org_id, environment_name):
        if not is_connector_usable(row.get("status")):
            continue
        vendor = str(row.get("vendor") or row.get("type") or "").strip().lower()
        if vendor:
            vendors.add(vendor)
    return vendors


def list_agents(client: Any, org_id: str) -> list[dict[str, Any]]:
    from app.operators.repository import list_operators

    return [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "status": row.get("status"),
            "role": row.get("role"),
            "requires_approval": bool(row.get("requires_approval")),
            "executionMode": row.get("execution_mode") or "plan_only",
            "autoExecuteTrustedScopes": list(row.get("auto_execute_trusted_scopes") or []),
            "capabilities": row.get("capabilities") or [],
            "provenance": "operators",
        }
        for row in list_operators(client, org_id)
    ]


def connector_readiness(vendor: str, connected: set[str] | None) -> Readiness:
    """``connected=None`` means no org context: connection state is unknown, not absent."""
    key = str(vendor or "").strip().lower()
    caps = list_actions(vendor=key)
    if not caps or not any(c.implemented for c in caps):
        return "MISSING"
    if connected is None or key not in connected:
        return "EXTERNAL_CONNECTION_REQUIRED"
    return "AVAILABLE"


def action_readiness(tool: str, connected: set[str] | None) -> Readiness:
    cap = get_action(tool)
    if cap is None:
        return "MISSING"
    if not cap.implemented:
        return "PARTIAL"
    if connected is None or cap.vendor not in connected:
        return "EXTERNAL_CONNECTION_REQUIRED"
    return "AVAILABLE"


def resolve_dependencies(
    *,
    connectors: Iterable[str] = (),
    actions: Iterable[str] = (),
    connected: set[str] | None = None,
) -> dict[str, Any]:
    connector_rows = {v: connector_readiness(v, connected) for v in connectors}
    action_rows = {}
    for tool in actions:
        cap = get_action(tool)
        action_rows[tool] = {
            "readiness": action_readiness(tool, connected),
            "access": cap.access if cap else None,
            "requires_approval": cap.requires_approval if cap else None,
            "verification_mode": cap.verification_mode if cap else None,
        }
    return {"connectors": connector_rows, "actions": action_rows}


CANONICAL_SOURCES = {
    "actions": "app.connectors.action_catalog.registry.get_vendor_catalog",
    "writeClassification": "app.services.catalog_write_authority.catalog_action_requires_write_approval",
    "runtimeWriteApproval": "app.services.write_governance.resolve_write_user_approval",
    "hitl": "hitl_policies via HitlPolicyService.resolve",
    "trust": "agent_identity_records.trust_level + approval_rule_overrides",
    "operatorWorkflowAutonomy": "operators.execution_mode + auto_execute_trusted_scopes (workflow auto-execute, not invoke_tool)",
    "connectors": "connectors table via list_connectors (status only; no token refresh)",
    "agents": "operators via list_operators",
    "workflowPrimitives": "app.workflows.constants.ALLOWED_STEP_TYPES",
    "events": "intelligence_outcome_path + outcome_learning_service + notification_emitter",
    "metrics": "app.services.cognitive_metrics",
    "verification": "app.services.write_success_verification",
    "evidence": "mapped existing stores (see evidence_sources)",
}


def tenant_capability_snapshot(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Authenticated org view. Status/readiness only — never tokens or connector config."""
    from app.connectors.repository import list_connectors as list_org_connectors
    from app.services.hitl_policy_service import HitlPolicyService
    from app.services.write_governance import snapshot_governance_fields

    connected = connected_vendors(client, org_id, environment_name)
    hitl = HitlPolicyService().resolve(
        client, org_id=str(org_id), user_id="", action_kind="write"
    )
    org_connectors: list[dict[str, Any]] = []
    for row in list_org_connectors(client, org_id, environment_name):
        vendor = str(row.get("vendor") or row.get("type") or "").strip().lower()
        org_connectors.append(
            {
                "id": row.get("id"),
                "orgId": row.get("org_id"),
                "vendor": vendor or None,
                "name": row.get("name"),
                "status": row.get("status"),
                "environment": row.get("environment"),
                "usable": is_connector_usable(row.get("status")),
                "readiness": connector_readiness(vendor, connected) if vendor else "MISSING",
            }
        )

    actions = []
    for cap in list_actions():
        write = cap.access == "write"
        actions.append(
            {
                **cap.as_dict(),
                "catalogRequiresWriteApproval": cap.requires_approval,
                "runtimeRequiresUserApproval": write,
                "runtimeApprovalNote": (
                    "WRITE requires user approval unless write_governance authorizes "
                    "this agent/context (autonomous + auto_run, and no covering HITL)."
                    if write
                    else "READ is not PendingAction-gated by default."
                ),
                "readiness": action_readiness(cap.tool, connected),
                "provenance": CANONICAL_SOURCES["actions"],
            }
        )

    return {
        "orgId": org_id,
        "environment": environment_name,
        "mutation": False,
        "sources": CANONICAL_SOURCES,
        "governance": snapshot_governance_fields(hitl=hitl),
        "agents": list_agents(client, org_id),
        "catalogConnectors": [
            {**c.as_dict(), "provenance": CANONICAL_SOURCES["actions"]}
            for c in list_catalog_connectors()
        ],
        "orgConnectors": org_connectors,
        "connectedVendors": sorted(connected),
        "actions": actions,
        "workflowPrimitives": workflow_primitives(),
        "events": event_taxonomy(),
        "metrics": business_metrics(client, org_id),
        "verification": verification_mechanisms(),
        "evidence": evidence_sources(),
        "unavailable": {
            "playSchema": "not implemented",
            "outcomeEventStore": "not a Play schema; see evidence OUTCOME stores",
            "dashboardTemplates": "not implemented",
        },
    }

