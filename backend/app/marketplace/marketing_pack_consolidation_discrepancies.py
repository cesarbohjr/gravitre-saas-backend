"""STA-298 / MKT-PACK-AUDIT: Post-consolidation discrepancies vs expected platform state."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

DiscrepancyState = Literal["confirmed", "partial", "resolved"]
DiscrepancyCategory = Literal["architecture", "naming", "compliance", "documentation", "execution"]

REPO_ROOT = Path(__file__).resolve().parents[3]
STA258_EVAL = REPO_ROOT / "docs" / "delivery" / "sta258-coordination-evaluation-latest.json"
COORDINATION_DIR = REPO_ROOT / "backend" / "app" / "coordination"
RETENTION_PURGE_SCRIPT = REPO_ROOT / "backend" / "scripts" / "retention_purge.py"
AUDIT_IMMUTABILITY_MIGRATION = (
    REPO_ROOT / "supabase" / "migrations" / "20260708130000_audit_retention_and_immutability.sql"
)
EXECUTE_PY = REPO_ROOT / "backend" / "app" / "workflows" / "execute.py"
AGENT_INTELLIGENCE_PY = REPO_ROOT / "backend" / "app" / "operators" / "agent_intelligence.py"
OAUTH_REGISTRY_PY = REPO_ROOT / "backend" / "app" / "connectors" / "oauth_provider_registry.py"
MARKETING_PACK_SLUG = "marketing-operations-pack"


@dataclass(frozen=True)
class ConsolidationDiscrepancy:
    key: str
    display_name: str
    category: DiscrepancyCategory
    audit_state: DiscrepancyState
    related_issue: str
    severity: Literal["info", "warning", "risk"]
    notes: str


CONSOLIDATION_DISCREPANCIES: tuple[ConsolidationDiscrepancy, ...] = (
    ConsolidationDiscrepancy(
        key="coordination_layer_killed",
        display_name="CoordinationLayer cut-over killed (not shipped)",
        category="architecture",
        audit_state="confirmed",
        related_issue="STA-258",
        severity="info",
        notes="STA-258 gate forcedOutcome=kill; backend/app/coordination/ removed; swarm/workflow wrappers remain.",
    ),
    ConsolidationDiscrepancy(
        key="execution_core_naming",
        display_name="ExecutionCore docs vs AgentIntelligence implementation",
        category="naming",
        audit_state="confirmed",
        related_issue="STA-284",
        severity="warning",
        notes="Universal execution is AgentIntelligence; ExecutionCore class absent but many string references still linger in code.",
    ),
    ConsolidationDiscrepancy(
        key="audit_retention_purge",
        display_name="Audit retention purge still deletes aged events",
        category="compliance",
        audit_state="confirmed",
        related_issue="STA-274",
        severity="risk",
        notes="Member RLS read-only shipped; retention_purge() still DELETEs audit_events/audit_logs after window.",
    ),
    ConsolidationDiscrepancy(
        key="connector_count_undercount",
        display_name="Connector brief undercount (~19 total vs 19 OAuth + 62 catalog)",
        category="documentation",
        audit_state="partial",
        related_issue="STA-292",
        severity="info",
        notes="19 OAuth providers in oauth_provider_registry; 62 action-catalog vendors — audit doc updated, brief may still undercount.",
    ),
    ConsolidationDiscrepancy(
        key="linear_execute_path_split",
        display_name="Graph canonical but linear step runner still separate",
        category="execution",
        audit_state="confirmed",
        related_issue="STA-259",
        severity="warning",
        notes="execute_workflow_steps delegates to graph when definition.graph present; linear steps path remains for legacy defs.",
    ),
)


def _module_source_path(module_path: str) -> Path | None:
    relative = module_path.replace(".", "/") + ".py"
    candidate = REPO_ROOT / "backend" / relative
    return candidate if candidate.is_file() else None


def _symbol_in_source(module_path: str, symbol: str) -> bool:
    source_path = _module_source_path(module_path)
    if source_path is None:
        return False
    text = source_path.read_text(encoding="utf-8")
    return f"def {symbol}" in text or f"class {symbol}" in text or f"async def {symbol}" in text


def _coordination_layer_module_shipped() -> bool:
    if not COORDINATION_DIR.is_dir():
        return False
    for path in COORDINATION_DIR.glob("*.py"):
        if path.name.startswith("_"):
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text and "class CoordinationLayer" in text:
            return True
    return False


def _coordination_layer_killed() -> bool:
    if _coordination_layer_module_shipped():
        return False
    if not STA258_EVAL.is_file():
        return not COORDINATION_DIR.is_dir()
    try:
        payload = json.loads(STA258_EVAL.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    gate = payload.get("gateDecision") or {}
    return str(gate.get("forcedOutcome") or "").lower() == "kill"


def _execution_core_naming_drift() -> DiscrepancyState:
    if not AGENT_INTELLIGENCE_PY.is_file():
        return "confirmed"
    agent_intel_text = AGENT_INTELLIGENCE_PY.read_text(encoding="utf-8")
    if "class AgentIntelligence" not in agent_intel_text:
        return "confirmed"
    if _symbol_in_source("app.operators.agent_intelligence", "ExecutionCore"):
        return "partial"
    backend_root = REPO_ROOT / "backend"
    if not backend_root.is_dir():
        return "confirmed"
    execution_core_refs = 0
    for path in backend_root.rglob("*.py"):
        if "marketing_pack_consolidation_discrepancies" in path.name:
            continue
        try:
            execution_core_refs += len(re.findall(r"\bExecutionCore\b", path.read_text(encoding="utf-8")))
        except OSError:
            continue
    if execution_core_refs == 0:
        return "resolved"
    if execution_core_refs <= 3:
        return "partial"
    return "confirmed"


def _audit_retention_purge_active() -> bool:
    if RETENTION_PURGE_SCRIPT.is_file():
        text = RETENTION_PURGE_SCRIPT.read_text(encoding="utf-8")
        if "retention_purge" in text:
            return True
    if AUDIT_IMMUTABILITY_MIGRATION.is_file():
        text = AUDIT_IMMUTABILITY_MIGRATION.read_text(encoding="utf-8")
        return "DELETE FROM public.audit_events" in text or "retention_purge" in text
    return False


def _audit_rls_read_only_shipped() -> bool:
    if not AUDIT_IMMUTABILITY_MIGRATION.is_file():
        return False
    text = AUDIT_IMMUTABILITY_MIGRATION.read_text(encoding="utf-8")
    return "audit_logs_org_read" in text and "audit_events_org_read" in text


def _connector_counts() -> tuple[int, int]:
    oauth_count = 0
    catalog_count = 0
    if OAUTH_REGISTRY_PY.is_file():
        text = OAUTH_REGISTRY_PY.read_text(encoding="utf-8")
        oauth_count = len(re.findall(r'^\s+"[a-z0-9_]+"\s*:\s*OAuthProviderSpec', text, re.MULTILINE))
        if oauth_count == 0:
            oauth_count = text.count("OAuthProviderSpec(")
    try:
        from app.connectors.action_catalog.registry import list_catalog_vendors

        catalog_count = len(list_catalog_vendors())
    except Exception:  # noqa: BLE001
        catalog_path = REPO_ROOT / "backend" / "app" / "connectors" / "action_catalog" / "vendor_definitions.py"
        if catalog_path.is_file():
            catalog_count = catalog_path.read_text(encoding="utf-8").count('"vendor":')
    return oauth_count, catalog_count


def _connector_count_discrepancy() -> DiscrepancyState:
    oauth_count, catalog_count = _connector_counts()
    if oauth_count >= 15 and catalog_count >= 50:
        return "confirmed"
    if oauth_count >= 10 and catalog_count >= 30:
        return "partial"
    return "resolved"


def _misleading_connector_total_docs() -> bool:
    audit_doc = REPO_ROOT / "docs" / "delivery" / "MARKETING_OPS_PACK_PHASE5-8_AUDIT.md"
    if audit_doc.is_file():
        text = audit_doc.read_text(encoding="utf-8")
        if "Undercount in brief" in text or "62" in text:
            return False
    return True


def _linear_execute_path_split() -> DiscrepancyState:
    if not EXECUTE_PY.is_file():
        return "resolved"
    text = EXECUTE_PY.read_text(encoding="utf-8")
    has_graph = "execute_workflow_graph" in text
    has_linear = "for idx, sdef in enumerate(steps_def):" in text
    if has_graph and has_linear:
        return "confirmed"
    if has_graph:
        return "partial"
    return "confirmed"


def _resolve_live_state(item: ConsolidationDiscrepancy) -> DiscrepancyState:
    if item.key == "coordination_layer_killed":
        return "confirmed" if _coordination_layer_killed() else "resolved"

    if item.key == "execution_core_naming":
        return _execution_core_naming_drift()

    if item.key == "audit_retention_purge":
        if not _audit_retention_purge_active():
            return "resolved"
        if _audit_rls_read_only_shipped():
            return "confirmed"
        return "partial"

    if item.key == "connector_count_undercount":
        state = _connector_count_discrepancy()
        if state == "confirmed" and not _misleading_connector_total_docs():
            return "partial"
        return state

    if item.key == "linear_execute_path_split":
        return _linear_execute_path_split()

    return item.audit_state


def audit_marketing_pack_consolidation_discrepancies() -> dict[str, Any]:
    """Return STA-298 discrepancy checklist with live verification."""
    rows: list[dict[str, Any]] = []
    confirmed_count = 0
    partial_count = 0
    resolved_count = 0
    risk_items: list[str] = []

    oauth_count, catalog_count = _connector_counts()

    for item in CONSOLIDATION_DISCREPANCIES:
        live_state = _resolve_live_state(item)
        if live_state == "confirmed":
            confirmed_count += 1
        elif live_state == "partial":
            partial_count += 1
        else:
            resolved_count += 1

        if item.severity == "risk" and live_state != "resolved":
            risk_items.append(item.key)

        rows.append(
            {
                "key": item.key,
                "displayName": item.display_name,
                "category": item.category,
                "relatedIssue": item.related_issue,
                "severity": item.severity,
                "documentedState": item.audit_state,
                "liveState": live_state,
                "stateMatchesDoc": live_state == item.audit_state,
                "notes": item.notes,
            }
        )

    architecture_rows = [row for row in rows if row["category"] == "architecture"]
    execution_rows = [row for row in rows if row["category"] in {"execution", "naming"}]
    compliance_doc_rows = [row for row in rows if row["category"] in {"compliance", "documentation"}]

    return {
        "issue": "STA-298",
        "packSlug": MARKETING_PACK_SLUG,
        "relatedIssues": ["STA-258", "STA-274", "STA-284", "STA-259", "STA-292"],
        "recommendation": (
            "Document discrepancies in onboarding/docs — do not assume CoordinationLayer or ExecutionCore "
            "names match runtime; connector inventory is 19 OAuth + 62 catalog vendors; graph is canonical "
            "but linear steps remain for legacy workflows"
        ),
        "summary": {
            "total": len(rows),
            "confirmed": confirmed_count,
            "partial": partial_count,
            "resolved": resolved_count,
            "riskItems": risk_items,
            "coordinationLayerKilled": _coordination_layer_killed(),
            "agentIntelligenceIsExecutionPath": AGENT_INTELLIGENCE_PY.is_file(),
            "auditRetentionPurgeActive": _audit_retention_purge_active(),
            "auditRlsReadOnlyShipped": _audit_rls_read_only_shipped(),
            "oauthProviderCount": oauth_count,
            "catalogVendorCount": catalog_count,
            "graphAndLinearExecutePaths": _linear_execute_path_split() == "confirmed",
            "openDiscrepancies": confirmed_count + partial_count,
        },
        "architecture": architecture_rows,
        "executionAndNaming": execution_rows,
        "complianceAndDocs": compliance_doc_rows,
        "discrepancies": rows,
    }
