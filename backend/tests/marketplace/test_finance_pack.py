"""Finance Intelligence Pack unit tests (scaffold — no live OAuth)."""
from __future__ import annotations

from app.marketplace.connector_category_templates import CONNECTOR_CATEGORY_TEMPLATES
from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec, list_intelligence_pack_specs
from app.services.tool_service import list_registered_actions


def test_finance_intelligence_pack_demo_in_catalog():
    spec = get_intelligence_pack_spec("finance-intelligence-pack")
    assert spec is not None
    assert spec.demo_agent_name == "Cash Flow Analyst"
    assert spec.connector_template_id == "finance-intelligence-sources"
    assert set(spec.demo_systems or []) >= {"quickbooks", "xero", "netsuite", "plaid"}
    actions = {s.get("config", {}).get("action") for s in (spec.workflow_steps or [])}
    assert "quickbooks.companyinfo.get" in actions
    assert "finance-intelligence-pack" in {s.pack_id for s in list_intelligence_pack_specs()}


def test_finance_intelligence_sources_template():
    tpl = CONNECTOR_CATEGORY_TEMPLATES["finance-intelligence-sources"]
    assert set(tpl["connectors"]) == {"quickbooks", "xero", "netsuite", "plaid"}


def test_finance_demo_actions_registered():
    registered = set(list_registered_actions())
    assert "quickbooks.companyinfo.get" in registered
    assert "xero.accounts.list" in registered
    assert "netsuite.invoices.list" in registered
    assert "plaid.accounts.get" in registered
