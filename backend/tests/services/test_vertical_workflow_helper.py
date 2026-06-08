"""Vertical workflow helper tests."""
from __future__ import annotations

import uuid

from app.services.legal_vertical_service import enrich_intake_parameters, intake_workflow_id
from app.services.vertical_workflow_helper import enrich_vertical_workflow_parameters


def test_enrich_vertical_routes_legal_workflow():
    org_id = str(uuid.uuid4())
    workflow_id = intake_workflow_id(org_id)
    out = enrich_vertical_workflow_parameters(
        org_id,
        workflow_id,
        {},
        {"config": {"legal": {"demo_matter_type": "Litigation"}}},
    )
    assert out["matter_type"] == "Litigation"
    assert out["prospect_name"] == "Acme Holdings LLC"
