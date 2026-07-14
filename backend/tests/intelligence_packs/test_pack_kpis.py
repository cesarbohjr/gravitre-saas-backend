"""Unit tests for Phase 3.5 pack KPI summary."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.intelligence_packs.shared.kpis import pack_kpi_summary


def test_pack_kpi_summary_empty_vendors_for_sales():
    client = MagicMock()
    # marketplace_assets miss → installed false
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    out = pack_kpi_summary(client, org_id="org-1", pack_id="sales-intelligence-pack")
    assert out["packId"] == "sales-intelligence-pack"
    assert out["installed"] is False
    assert out["signalsCount"] == 0
    assert out["vendors"] == {}


def test_pack_kpi_summary_counts_executive_vendors():
    client = MagicMock()

    def table(name: str):
        m = MagicMock()
        if name == "marketplace_assets":
            m.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "asset-1", "slug": "executive-intelligence-pack"}]
            )
        elif name == "marketplace_installs":
            chain = m.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value
            chain.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "inst-1",
                        "status": "active",
                        "metadata": {"agentId": "a1", "workflowId": "w1"},
                    }
                ]
            )
        else:
            # external_signals / external_entities / assignments — count path
            chain = m.select.return_value.eq.return_value
            # may call .in_ or .eq vendor then .limit
            chain.in_.return_value.limit.return_value.execute.return_value = MagicMock(count=3, data=[])
            chain.eq.return_value.limit.return_value.execute.return_value = MagicMock(count=2, data=[])
            chain.not_.is_.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
                count=1, data=[]
            )
            chain.not_.is_.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                count=1, data=[]
            )
            chain.contains.return_value.limit.return_value.execute.return_value = MagicMock(count=4, data=[])
        return m

    client.table.side_effect = table
    out = pack_kpi_summary(client, org_id="org-1", pack_id="executive-intelligence-pack")
    assert out["installed"] is True
    assert out["agentCount"] == 1
    assert out["workflowCount"] == 1
    assert "fred" in out["vendors"]
