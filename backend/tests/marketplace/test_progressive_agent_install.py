"""Every seeded agent can install offline without bypassing version/IAM gates."""
from copy import deepcopy
from dataclasses import asdict
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.marketplace.browse import _checklist_summary
from app.marketplace.seed_catalog import list_catalog_assets
from app.marketplace.service import install_asset, preview_install
from tests.marketplace.test_approved_agency_enrichment import db

AGENTS = tuple(a for a in list_catalog_assets() if a.asset_type == "ai_agent")


@pytest.mark.parametrize("asset", AGENTS, ids=lambda a: a.slug)
def test_catalog_agent_offline_install_preview_and_browse_agree(db, asset):
    row = {**asdict(asset), "id": str(uuid5(NAMESPACE_URL, asset.slug)),
           "visibility": "public", "status": "published", "current_version": 1,
           "org_id": None, "required_permissions": []}
    db.tables["marketplace_assets"] = [row]
    db.tables["marketplace_asset_versions"] = [{
        "asset_id": row["id"], "version_number": 1, "published_at": "2026-10-28T00:00:00Z",
        **{key: deepcopy(row[key]) for key in ("config", "required_connectors", "required_permissions", "install_variables")},
    }]
    preview = preview_install(db, "org-a", row["id"], environment_name="test")
    assert preview["canInstall"] and not preview["blockers"]
    summary = _checklist_summary(row["required_connectors"], {
        "can_install": False, "checklist": preview["connectorChecklist"],
    }, asset=row)
    assert summary["canInstall"]
    result = install_asset(db, "org-a", row["id"], actor_id="admin", environment_name="test")
    assert result["installed"]
    assert not db.tables.get("connectors")
    assert not any(item["connected"] for item in result["connectorChecklist"])
    agent_id = result["entities"]["agentId"]
    again = install_asset(db, "org-a", row["id"], actor_id="admin", environment_name="test", version_number=1)
    assert again["entities"]["agentId"] == agent_id
