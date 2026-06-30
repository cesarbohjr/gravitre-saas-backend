"""STA-295 / MKT-PACK-AUDIT 7.1: Marketing pack brand/positioning knowledge store audit."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

BrandKnowledgeState = Literal["exists", "partial", "missing"]
PackBlocker = Literal["yes", "no", "depends"]

REPO_ROOT = Path(__file__).resolve().parents[3]
DEPARTMENT_RAG_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260602130000_department_scoped_rag.sql"
MARKETING_PACK_SLUG = "marketing-operations-pack"
BRAND_VOICE_SEED_LABEL = "rag:brand-voice"


@dataclass(frozen=True)
class BrandKnowledgeCapability:
    key: str
    display_name: str
    audit_state: BrandKnowledgeState
    complexity: Literal["low", "medium", "high"]
    blocks_pack: PackBlocker
    notes: str
    module_path: str | None = None
    symbol: str | None = None


BRAND_KNOWLEDGE_CAPABILITIES: tuple[BrandKnowledgeCapability, ...] = (
    BrandKnowledgeCapability(
        key="unified_retrieval_service",
        display_name="UnifiedRetrievalService (RAG + org + memory)",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="Single retrieval path for AgentIntelligence; knowledge scope uses RAGService.",
        module_path="app.services.unified_retrieval_service",
        symbol="UnifiedRetrievalService",
    ),
    BrandKnowledgeCapability(
        key="department_scoped_rag_migration",
        display_name="Department-scoped RAG schema",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="Migration 20260602130000 adds department_id/agent_id to rag_sources and rag_search filter.",
    ),
    BrandKnowledgeCapability(
        key="rag_department_filtering",
        display_name="RAG department/agent filtering at retrieval",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        notes="rag_service.resolve_department_id_for_agent + scope agent/department; pack install must upload docs.",
        module_path="app.rag.department",
        symbol="resolve_department_id_for_agent",
    ),
    BrandKnowledgeCapability(
        key="agent_intelligence_retrieval_wiring",
        display_name="AgentIntelligence uses unified retrieval",
        audit_state="exists",
        complexity="low",
        blocks_pack="no",
        notes="agent_intelligence.py imports get_unified_retrieval_service for task runs.",
        module_path="app.operators.agent_intelligence",
        symbol="UnifiedRetrievalService",
    ),
    BrandKnowledgeCapability(
        key="pack_brand_voice_seed",
        display_name="Marketing pack brand-voice RAG placeholder",
        audit_state="partial",
        complexity="low",
        blocks_pack="depends",
        notes="department_pack config seeds rag:brand-voice doc; customer uploads content post-install.",
    ),
    BrandKnowledgeCapability(
        key="marketing_knowledge_pack",
        display_name="Marketing operations knowledge pack",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        notes="Standalone knowledge_pack includes Brand Voice Guide + Campaign Playbooks placeholders.",
    ),
    BrandKnowledgeCapability(
        key="structured_brand_store",
        display_name="Structured brand/positioning store (non-RAG)",
        audit_state="missing",
        complexity="high",
        blocks_pack="no",
        notes="Not required for v1; recommendation is RAG-source-based brand knowledge only.",
    ),
    BrandKnowledgeCapability(
        key="pack_scoped_brand_primitive",
        display_name="Pack-scoped brand primitive API",
        audit_state="missing",
        complexity="medium",
        blocks_pack="no",
        notes="No dedicated brand store table or pack-scoped schema beyond RAG source metadata.",
    ),
)


def _module_loaded(module_path: str) -> bool:
    return importlib.util.find_spec(module_path) is not None


def _symbol_exists(module_path: str, symbol: str) -> bool:
    if not _module_loaded(module_path):
        return False
    module = importlib.import_module(module_path)
    return getattr(module, symbol, None) is not None


def _migration_has_department_scoped_rag() -> bool:
    if not DEPARTMENT_RAG_MIGRATION.is_file():
        return False
    text = DEPARTMENT_RAG_MIGRATION.read_text(encoding="utf-8")
    return "p_department_id" in text and "department_id" in text


def _marketing_pack_has_brand_voice_seed() -> bool:
    from app.marketplace.seed_catalog import catalog_assets_by_slug

    pack = catalog_assets_by_slug().get(MARKETING_PACK_SLUG)
    if not pack:
        return False
    rag_sources = (pack.config or {}).get("rag_sources") or []
    for source in rag_sources:
        if str(source.get("seed_label") or "") == BRAND_VOICE_SEED_LABEL:
            return True
    return False


def _marketing_knowledge_pack_has_brand_voice() -> bool:
    from app.marketplace.seed_catalog import catalog_assets_by_slug

    pack = catalog_assets_by_slug().get("marketing-operations-knowledge")
    if not pack:
        return False
    documents = (pack.config or {}).get("documents") or []
    return any(str(doc.get("seed_label") or "") == BRAND_VOICE_SEED_LABEL for doc in documents)


def _resolve_live_state(cap: BrandKnowledgeCapability) -> BrandKnowledgeState:
    if cap.key == "department_scoped_rag_migration":
        return "exists" if _migration_has_department_scoped_rag() else "missing"

    if cap.key == "pack_brand_voice_seed":
        return "partial" if _marketing_pack_has_brand_voice_seed() else "missing"

    if cap.key == "marketing_knowledge_pack":
        return "partial" if _marketing_knowledge_pack_has_brand_voice() else "missing"

    if cap.key in {"structured_brand_store", "pack_scoped_brand_primitive"}:
        return "missing"

    if cap.module_path and cap.symbol:
        if not _symbol_exists(cap.module_path, cap.symbol):
            return "missing"
        return cap.audit_state

    return cap.audit_state


def audit_marketing_pack_brand_knowledge() -> dict[str, Any]:
    """Return STA-295 checklist with live code verification."""
    rows: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    exists_count = 0
    pack_blockers: list[str] = []

    for cap in BRAND_KNOWLEDGE_CAPABILITIES:
        live_state = _resolve_live_state(cap)
        if live_state == "missing":
            missing_count += 1
        elif live_state == "partial":
            partial_count += 1
        else:
            exists_count += 1
        if cap.blocks_pack == "yes" and live_state != "exists":
            pack_blockers.append(cap.key)
        elif cap.key == "pack_brand_voice_seed" and live_state == "missing":
            pack_blockers.append(cap.key)

        rows.append(
            {
                "key": cap.key,
                "displayName": cap.display_name,
                "documentedState": cap.audit_state,
                "liveState": live_state,
                "stateMatchesDoc": live_state == cap.audit_state,
                "complexity": cap.complexity,
                "blocksPack": cap.blocks_pack,
                "notes": cap.notes,
            }
        )

    return {
        "issue": "STA-295",
        "packSlug": MARKETING_PACK_SLUG,
        "recommendation": "RAG-source-based brand knowledge via UnifiedRetrievalService + department-scoped RAG",
        "v1StructuredBrandStoreRequired": False,
        "brandVoiceSeedLabel": BRAND_VOICE_SEED_LABEL,
        "summary": {
            "total": len(rows),
            "missing": missing_count,
            "partial": partial_count,
            "exists": exists_count,
            "packBlockers": pack_blockers,
            "v1Ready": len(pack_blockers) == 0 and missing_count <= 2,
        },
        "capabilities": rows,
    }
