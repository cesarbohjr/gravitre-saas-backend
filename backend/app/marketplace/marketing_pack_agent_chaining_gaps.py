"""STA-291 / MKT-PACK-AUDIT 5.1: Marketing pack agent chaining + department_pack mapping audit."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ChainGapState = Literal["exists", "partial", "missing"]
PackBlocker = Literal["yes", "no", "depends"]
CapabilityCategory = Literal["catalog", "runtime", "versioning"]

REPO_ROOT = Path(__file__).resolve().parents[3]
MARKETING_PACK_SLUG = "marketing-operations-pack"
INSTALL_SMOKE_SCRIPT = REPO_ROOT / "scripts" / "smoke-marketing-operations-pack-install.py"
EXPECTED_AGENT_SLUGS = frozenset(
    {
        "product-icp-strategist",
        "content-writer",
        "marketing-designer",
        "marketing-ops-coordinator",
    }
)


@dataclass(frozen=True)
class AgentChainingCapability:
    key: str
    display_name: str
    category: CapabilityCategory
    audit_state: ChainGapState
    complexity: Literal["low", "medium", "high"]
    blocks_pack: PackBlocker
    notes: str
    module_path: str | None = None
    symbol: str | None = None


AGENT_CHAINING_CAPABILITIES: tuple[AgentChainingCapability, ...] = (
    AgentChainingCapability(
        key="department_pack_asset_type",
        display_name="department_pack marketplace asset type",
        category="catalog",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="schemas.py DepartmentPackAssetConfig + publish validation.",
        module_path="app.marketplace.schemas",
        symbol="DepartmentPackAssetConfig",
    ),
    AgentChainingCapability(
        key="four_agent_marketing_pack_seed",
        display_name="Marketing pack 4-agent seed catalog",
        category="catalog",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        notes="marketing-operations-pack seeds 4 agents + campaign workflow in seed_catalog.py.",
    ),
    AgentChainingCapability(
        key="workflow_handoff_next_agent_seed",
        display_name="Workflow handoff steps (next_agent_seed)",
        category="catalog",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="Two agent steps chain ICP -> content -> design -> ops via next_agent_seed metadata.",
    ),
    AgentChainingCapability(
        key="install_next_agent_resolution",
        display_name="Install resolves next_agent_seed to org agent UUIDs",
        category="runtime",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        notes="_install_department_pack maps next_agent_seed to next_agent_id at install.",
        module_path="app.marketplace.service",
        symbol="_install_department_pack",
    ),
    AgentChainingCapability(
        key="handoff_service_execution",
        display_name="Handoff service executes chained agent steps",
        category="runtime",
        audit_state="exists",
        complexity="medium",
        blocks_pack="no",
        notes="execute_agent_step_with_handoff routes to next_agent_id with briefing.",
        module_path="app.services.handoff_service",
        symbol="execute_agent_step_with_handoff",
    ),
    AgentChainingCapability(
        key="standalone_agent_catalog_entries",
        display_name="Standalone ai_agent catalog entries for chain members",
        category="catalog",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="pack_children includes 4 agent slugs + workflow + knowledge pack.",
    ),
    AgentChainingCapability(
        key="install_smoke_script",
        display_name="Staging install + handoff smoke script",
        category="runtime",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="scripts/smoke-marketing-operations-pack-install.py (STA-291).",
    ),
    AgentChainingCapability(
        key="pack_coordinated_semver",
        display_name="Pack-coordinated semver across chain members",
        category="versioning",
        audit_state="missing",
        complexity="high",
        blocks_pack="depends",
        notes="Per-agent versioning only; no coordinated pack rollback (STA-296).",
    ),
)

ALL_AGENT_CHAINING_CAPABILITIES = AGENT_CHAINING_CAPABILITIES


def _module_source_path(module_path: str) -> Path | None:
    relative = module_path.replace(".", "/") + ".py"
    candidate = REPO_ROOT / "backend" / relative
    return candidate if candidate.is_file() else None


def _symbol_exists(module_path: str, symbol: str) -> bool:
    source_path = _module_source_path(module_path)
    if source_path is not None:
        text = source_path.read_text(encoding="utf-8")
        return f"def {symbol}" in text or f"class {symbol}" in text or f"async def {symbol}" in text
    if importlib.util.find_spec(module_path) is None:
        return False
    module = importlib.import_module(module_path)
    return getattr(module, symbol, None) is not None


def _marketing_pack_seed() -> Any | None:
    try:
        from app.marketplace.seed_catalog import catalog_assets_by_slug

        return catalog_assets_by_slug().get(MARKETING_PACK_SLUG)
    except Exception:  # noqa: BLE001
        return None


def _four_agent_seed_shipped() -> bool:
    pack = _marketing_pack_seed()
    if pack is None:
        return False
    agents = (pack.config or {}).get("agents") or []
    if len(agents) != 4:
        return False
    slugs = {str(agent.get("config", {}).get("marketplaceSlug") or "") for agent in agents}
    return EXPECTED_AGENT_SLUGS.issubset(slugs)


def _handoff_steps_shipped() -> bool:
    pack = _marketing_pack_seed()
    if pack is None:
        return False
    steps = (pack.config or {}).get("workflow_steps") or []
    handoffs = [step for step in steps if (step.get("metadata") or {}).get("next_agent_seed")]
    return len(handoffs) >= 2


def _standalone_agents_in_pack_children() -> bool:
    pack = _marketing_pack_seed()
    if pack is None:
        return False
    children = set(pack.pack_children or [])
    return EXPECTED_AGENT_SLUGS.issubset(children)


def _install_resolves_next_agent_seed() -> bool:
    service_path = _module_source_path("app.marketplace.service")
    if service_path is None:
        return False
    text = service_path.read_text(encoding="utf-8")
    return "next_agent_seed" in text and "next_agent_id" in text


def _pack_coordinated_semver_shipped() -> bool:
    service_path = _module_source_path("app.marketplace.service")
    if service_path is None:
        return False
    text = service_path.read_text(encoding="utf-8")
    markers = ("pack_coordinated_semver", "rollback_department_pack", "pack_install_snapshot")
    return any(marker in text for marker in markers)


def _resolve_live_state(cap: AgentChainingCapability) -> ChainGapState:
    if cap.key == "four_agent_marketing_pack_seed":
        return "exists" if _four_agent_seed_shipped() else "missing"

    if cap.key == "workflow_handoff_next_agent_seed":
        return "exists" if _handoff_steps_shipped() else "missing"

    if cap.key == "install_next_agent_resolution":
        return "exists" if _install_resolves_next_agent_seed() else "missing"

    if cap.key == "standalone_agent_catalog_entries":
        return "exists" if _standalone_agents_in_pack_children() else "partial"

    if cap.key == "install_smoke_script":
        return "exists" if INSTALL_SMOKE_SCRIPT.is_file() else "missing"

    if cap.key == "pack_coordinated_semver":
        return "exists" if _pack_coordinated_semver_shipped() else "missing"

    if cap.module_path and cap.symbol:
        if not _symbol_exists(cap.module_path, cap.symbol):
            return "missing"
        return cap.audit_state

    return cap.audit_state


def audit_marketing_pack_agent_chaining() -> dict[str, Any]:
    """Return STA-291 checklist with live code verification."""
    rows: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    exists_count = 0
    pack_blockers: list[str] = []

    for cap in ALL_AGENT_CHAINING_CAPABILITIES:
        live_state = _resolve_live_state(cap)
        if live_state == "missing":
            missing_count += 1
        elif live_state == "partial":
            partial_count += 1
        else:
            exists_count += 1

        if cap.blocks_pack == "yes" and live_state != "exists":
            pack_blockers.append(cap.key)

        rows.append(
            {
                "key": cap.key,
                "displayName": cap.display_name,
                "category": cap.category,
                "documentedState": cap.audit_state,
                "liveState": live_state,
                "stateMatchesDoc": live_state == cap.audit_state,
                "complexity": cap.complexity,
                "blocksPack": cap.blocks_pack,
                "notes": cap.notes,
            }
        )

    catalog_rows = [row for row in rows if row["category"] == "catalog"]
    runtime_rows = [row for row in rows if row["category"] == "runtime"]
    versioning_rows = [row for row in rows if row["category"] == "versioning"]

    return {
        "issue": "STA-291",
        "packSlug": MARKETING_PACK_SLUG,
        "relatedIssues": ["STA-296", "STA-259", "STA-18"],
        "recommendation": (
            "v1: 4-agent chain + handoff install path is shippable; defer pack-coordinated semver "
            "until product requires coordinated rollback across chain members"
        ),
        "summary": {
            "total": len(rows),
            "missing": missing_count,
            "partial": partial_count,
            "exists": exists_count,
            "packBlockers": pack_blockers,
            "fourAgentSeedShipped": _four_agent_seed_shipped(),
            "handoffStepsShipped": _handoff_steps_shipped(),
            "installSmokeScriptShipped": INSTALL_SMOKE_SCRIPT.is_file(),
            "packCoordinatedSemverMissing": not _pack_coordinated_semver_shipped(),
            "v1Ready": len(pack_blockers) == 0,
        },
        "catalog": catalog_rows,
        "runtime": runtime_rows,
        "versioning": versioning_rows,
        "capabilities": rows,
    }
