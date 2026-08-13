"""Process-mining SUGGEST-ONLY — never auto-adopt as governing reality."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.process_mining_service import ProcessMiningService


def _settings():
    return MagicMock()


def _chain_insert(data):
    result = MagicMock()
    result.data = data
    insert = MagicMock()
    insert.execute.return_value = result
    return insert


@pytest.mark.asyncio
async def test_suggest_process_sequences_advisory_only_never_auto_adopt():
    svc = ProcessMiningService(settings=_settings())
    patterns = {
        "status": "ok",
        "advisory_only": True,
        "auto_adopted": False,
        "patterns": [
            {"sequence": "Intake → Review → Approve", "occurrences": 5},
            {"sequence": "Rare → Path", "occurrences": 1},
        ],
    }
    client = MagicMock()
    # No existing pending suggestion
    select_chain = (
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value
    )
    select_chain.execute.return_value.data = []
    inserted_rows: list[dict] = []

    def _insert(row):
        inserted_rows.append(row)
        return _chain_insert([{**row, "id": f"sug-{len(inserted_rows)}"}])

    client.table.return_value.insert.side_effect = _insert

    with (
        patch.object(svc, "discover_workflow_patterns", return_value=patterns),
        patch.object(svc, "_client", return_value=client),
    ):
        result = await svc.suggest_process_sequences("org-1", min_occurrences=3)

    assert result["advisory_only"] is True
    assert result["auto_adopted"] is False
    assert result["suggestions_created"] == 1
    assert inserted_rows[0]["suggestion_type"] == "process_sequence"
    assert inserted_rows[0]["status"] == "pending_review"
    assert inserted_rows[0]["evidence"]["advisory_only"] is True
    assert inserted_rows[0]["evidence"]["auto_adopted"] is False
    # Must not touch inventory on suggest
    table_names = [c.args[0] for c in client.table.call_args_list]
    assert "organization_process_inventory" not in table_names


@pytest.mark.asyncio
async def test_discover_never_writes_inventory():
    svc = ProcessMiningService(settings=_settings())
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.gte.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    with (
        patch.object(svc, "_client", return_value=client),
        patch(
            "app.services.process_mining_service.collect_workflow_run_features",
            return_value=[],
        ),
    ):
        result = await svc.discover_workflow_patterns("org-1")

    assert result["advisory_only"] is True
    assert result["auto_adopted"] is False
    assert client.table.return_value.insert.call_count == 0


@pytest.mark.asyncio
async def test_accept_copies_to_inventory_only_on_admin_accept():
    svc = ProcessMiningService(settings=_settings())
    suggestion = {
        "id": "sug-1",
        "org_id": "org-1",
        "suggestion_type": "process_sequence",
        "status": "pending_review",
        "target_entity_id": "A → B → C",
        "evidence": {
            "sequence": "A → B → C",
            "steps": ["A", "B", "C"],
            "department": "Sales",
            "advisory_only": True,
            "auto_adopted": False,
        },
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        suggestion
    ]
    inv_insert = _chain_insert(
        [{"id": "inv-1", "org_id": "org-1", "process_name": "Observed: A → B → C", "department": "Sales"}]
    )
    sug_update = _chain_insert([{**suggestion, "status": "applied"}])

    def _table(name: str):
        t = MagicMock()
        if name == "optimization_suggestions":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                suggestion
            ]
            t.update.return_value.eq.return_value.eq.return_value.execute.return_value = sug_update.execute.return_value
            t.update.return_value.eq.return_value.eq.return_value = sug_update
            # chain: update().eq().eq().execute()
            upd = MagicMock()
            eq2 = MagicMock()
            eq2.execute.return_value = MagicMock(data=[{**suggestion, "status": "applied"}])
            upd.eq.return_value.eq.return_value = eq2
            # Actually need update().eq().eq().execute
            chain = MagicMock()
            chain.eq.return_value.eq.return_value.execute.return_value.data = [
                {**suggestion, "status": "applied"}
            ]
            t.update.return_value = chain
        elif name == "organization_process_inventory":
            t.insert.return_value = inv_insert
        return t

    client.table.side_effect = _table

    with patch.object(svc, "_client", return_value=client):
        result = await svc.accept_process_sequence_suggestion(
            "org-1",
            "sug-1",
            reviewed_by="admin-1",
        )

    assert result["advisory_only"] is True
    assert result["auto_adopted"] is False
    assert result["inventoryEntry"]["id"] == "inv-1"


def test_process_mining_has_no_auto_adopt_method():
    svc = ProcessMiningService(settings=_settings())
    assert not hasattr(svc, "auto_adopt_process_sequences")
    assert not hasattr(svc, "auto_apply_to_inventory")
