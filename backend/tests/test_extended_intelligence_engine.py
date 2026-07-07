"""Extended Intelligence Engine — v6/v4/v8/v10 extensions (no parallel platforms)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.operators.agent_prompts import AGENT_PERSONAS
from app.services.answer_explanation import generate_suggestion_explanation
from app.services.entity_relationship_builder import (
    ENTITY_DEAL,
    build_relationships_from_crm_data,
)
from app.services.outcome_attribution_service import (
    CONFIDENCE_NOTE,
    MIN_SAMPLE_SIZE,
    ATTRIBUTION_WINDOWS_BY_ACTION_TYPE,
    METRIC_INVOICE_BALANCE,
    maybe_record_quickbooks_invoice_outcome_baseline,
)
from app.services.tool_types import ToolContext


@pytest.mark.asyncio
async def test_crm_entities_added_to_existing_relationship_table():
    client = MagicMock()
    captured: list[dict] = []

    def table(name):
        t = MagicMock()
        if name == "agent_action_outcomes":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "agent_id": "agent-1",
                        "workflow_run_id": "run-1",
                        "target_entity_type": "deal",
                        "target_entity_id": "deal-99",
                        "action_type": "hubspot.deals.update",
                    }
                ]
            )
        return t

    client.table.side_effect = table
    with patch(
        "app.services.entity_relationship_builder._upsert_relationship",
        side_effect=lambda db, **kwargs: captured.append(kwargs) or True,
    ):
        count = await build_relationships_from_crm_data("org-1", client=client)
    assert count >= 1
    assert all(row["source_entity_type"] == ENTITY_DEAL for row in captured if row["source_entity_type"] == ENTITY_DEAL)


def test_no_new_relationship_table_created():
    migrations = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
    text = " ".join(p.read_text(encoding="utf-8") for p in migrations.glob("*.sql"))
    assert "business_entities" not in text
    assert "business_relationships" not in text
    assert "CREATE TABLE IF NOT EXISTS public.org_entity_relationships" in text


@pytest.mark.asyncio
async def test_one_hop_limit_still_enforced_for_business_entities():
    from app.services.entity_relationship_service import get_related_entities

    client = MagicMock()
    hops = [{"target_entity_type": "deal", "target_entity_id": "d2", "confidence": 0.9, "evidence_count": 2}]

    def table(name):
        t = MagicMock()
        if name == "org_entity_relationships":
            t.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "relationship_type": "tracked-by",
                        "target_entity_type": "agent",
                        "target_entity_id": "agent-1",
                        "confidence": 0.8,
                        "evidence_count": 1,
                    }
                ]
            )
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return t

    client.table.side_effect = table
    related = await get_related_entities("org-1", "deal", "deal-1", max_results=5, client=client)
    assert len(related) <= 5
    assert related[0]["entityType"] == "agent"


def test_no_duplicate_memory_system():
    migrations = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
    text = " ".join(p.read_text(encoding="utf-8") for p in migrations.glob("*.sql"))
    assert "organizational_memory" not in text
    assert "memory_events" not in text


def test_no_duplicate_outcome_attribution_table():
    migrations = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
    text = " ".join(p.read_text(encoding="utf-8") for p in migrations.glob("*.sql"))
    assert "ai_outcomes" not in text
    assert "outcome_attribution" not in text.lower() or "agent_action_outcomes" in text


def test_no_separate_agent_runtime_module_created():
    backend_root = Path(__file__).resolve().parents[1] / "app"
    assert not (backend_root / "agent_runtime").exists()


def test_digital_twin_simulation_explicitly_not_claimed_anywhere():
    backend_root = Path(__file__).resolve().parents[1]
    forbidden_phrases = (
        "what happens if we increase marketing spend",
        "organizational simulation engine",
        "predictive digital twin",
    )
    for path in backend_root.rglob("*.py"):
        if "test_" in path.name:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            assert phrase not in text, f"forbidden simulation claim in {path}"


def test_new_metric_types_still_require_confidence_note():
    ctx = ToolContext(
        org_id="org-1",
        agent_id="agent-1",
        run_id="run-1",
        actor_id="user-1",
        client=MagicMock(),
        settings=MagicMock(),
    )
    client = MagicMock()
    with patch("app.services.outcome_attribution_service.OutcomeAttributionService._client", return_value=client):
        maybe_record_quickbooks_invoice_outcome_baseline(
            ctx,
            invoice_id="inv-1",
            action_type="quickbooks.invoices.create",
            invoice_payload={"Invoice": {"Id": "inv-1", "Balance": 120.0}},
        )
    payload = client.table.return_value.insert.call_args[0][0]
    assert payload["confidence_note"] == CONFIDENCE_NOTE
    assert payload["metric_name"] == METRIC_INVOICE_BALANCE


def test_new_metric_types_still_gated_by_min_sample():
    assert MIN_SAMPLE_SIZE >= 15
    assert ATTRIBUTION_WINDOWS_BY_ACTION_TYPE["quickbooks.invoices.create"] == 30


def test_no_reward_function_or_rl_logic_introduced():
    path = Path(__file__).resolve().parents[1] / "app" / "services" / "outcome_attribution_service.py"
    text = path.read_text(encoding="utf-8").lower()
    assert "reinforcement" in text
    assert "reward_function" not in text
    assert "policy_gradient" not in text


def test_meta_agent_personas_exist_without_new_runtime():
    assert "PLANNER" in AGENT_PERSONAS
    assert "VALIDATOR" in AGENT_PERSONAS


def test_suggestion_explanation_is_audit_readable():
    text = generate_suggestion_explanation(
        {
            "suggestion_type": "stalled_deal",
            "evidence": {
                "source": "agent_action_outcomes",
                "sample_size": 18,
                "confidence_note": "correlational only",
            },
        }
    )
    assert "stalled deal" in text.lower()
    assert "correlational" in text.lower()
    assert "chain" not in text.lower()


def test_organization_process_inventory_migration_present():
    migration = (
        Path(__file__).resolve().parents[2]
        / "supabase"
        / "migrations"
        / "20260709200000_extended_intelligence_engine.sql"
    )
    text = migration.read_text(encoding="utf-8")
    assert "organization_process_inventory" in text
    assert "simulation" in text.lower()

    conformance_migration = (
        Path(__file__).resolve().parents[2]
        / "supabase"
        / "migrations"
        / "20260705050000_process_inventory_conformance_columns.sql"
    )
    conformance_text = conformance_migration.read_text(encoding="utf-8")
    assert "workflow_id" in conformance_text
    assert "declared_steps" in conformance_text
