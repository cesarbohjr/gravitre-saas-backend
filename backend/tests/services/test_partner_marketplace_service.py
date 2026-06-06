"""Partner marketplace service tests (STA-71)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.partner_marketplace_service import (
    create_submission,
    list_registry,
    review_submission,
    validate_security_checklist,
)

EXAMPLE_MANIFEST = json.loads(
    Path(__file__).resolve().parents[3].joinpath("docs/integration/examples/acme-tools/manifest.json").read_text(
        encoding="utf-8"
    )
)

CHECKLIST = {
    "no_hardcoded_secrets": True,
    "oauth_redirects_documented": True,
    "scopes_minimized": True,
    "data_residency_documented": True,
    "audit_logging_compatible": True,
    "error_handling_documented": True,
}


def _chainable(data):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.execute.return_value = MagicMock(data=data)
    return chain


def test_validate_security_checklist_requires_all():
    with pytest.raises(HTTPException) as exc:
        validate_security_checklist({"no_hardcoded_secrets": True})
    assert exc.value.status_code == 400


def test_create_submission_inserts_row():
    client = MagicMock()
    client.table.side_effect = [
        _chainable([]),  # conflict check
        _chainable([]),  # published check
        _chainable(
            [
                {
                    "id": "sub-1",
                    "org_id": "org-1",
                    "submitted_by": "user-1",
                    "package_id": EXAMPLE_MANIFEST["id"],
                    "vendor": EXAMPLE_MANIFEST["vendor"],
                    "name": EXAMPLE_MANIFEST["name"],
                    "version": EXAMPLE_MANIFEST["version"],
                    "manifest": EXAMPLE_MANIFEST,
                    "security_checklist": CHECKLIST,
                    "status": "pending",
                    "reviewer_id": None,
                    "review_notes": None,
                    "reviewed_at": None,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ]
        ),
    ]
    row = create_submission(
        client,
        org_id="org-1",
        submitted_by="user-1",
        manifest=EXAMPLE_MANIFEST,
        security_checklist=CHECKLIST,
    )
    assert row["vendor"] == "acme_tools"
    assert row["status"] == "pending"


def test_review_submission_approve_publishes_registry():
    submission_row = {
        "id": "sub-1",
        "org_id": "org-1",
        "submitted_by": "user-1",
        "package_id": EXAMPLE_MANIFEST["id"],
        "vendor": EXAMPLE_MANIFEST["vendor"],
        "name": EXAMPLE_MANIFEST["name"],
        "version": EXAMPLE_MANIFEST["version"],
        "manifest": EXAMPLE_MANIFEST,
        "security_checklist": CHECKLIST,
        "status": "pending",
        "reviewer_id": None,
        "review_notes": None,
        "reviewed_at": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    registry_row = {
        "id": "reg-1",
        "submission_id": "sub-1",
        "org_id": "org-1",
        "package_id": EXAMPLE_MANIFEST["id"],
        "vendor": EXAMPLE_MANIFEST["vendor"],
        "name": EXAMPLE_MANIFEST["name"],
        "version": EXAMPLE_MANIFEST["version"],
        "manifest": EXAMPLE_MANIFEST,
        "published_by": "admin-1",
        "published_at": "2026-01-02T00:00:00Z",
        "status": "published",
    }
    client = MagicMock()
    client.table.side_effect = [
        _chainable([submission_row]),  # fetch submission
        _chainable([{**submission_row, "status": "approved"}]),  # update submission
        _chainable([registry_row]),  # insert registry
    ]
    result = review_submission(
        client,
        submission_id="sub-1",
        reviewer_id="admin-1",
        org_id="org-1",
        decision="approve",
        notes="Looks good",
    )
    assert result["submission"]["status"] == "approved"
    assert result["registry"]["vendor"] == "acme_tools"


def test_list_registry_returns_published():
    client = MagicMock()
    client.table.return_value = _chainable(
        [
            {
                "id": "reg-1",
                "submission_id": "sub-1",
                "org_id": "org-1",
                "package_id": "com.acme.tools",
                "vendor": "acme_tools",
                "name": "Acme Tools",
                "version": "1.0.0",
                "manifest": EXAMPLE_MANIFEST,
                "published_by": "admin-1",
                "published_at": "2026-01-02T00:00:00Z",
                "status": "published",
            }
        ]
    )
    rows = list_registry(client)
    assert rows[0]["authType"] == "apiKey"
