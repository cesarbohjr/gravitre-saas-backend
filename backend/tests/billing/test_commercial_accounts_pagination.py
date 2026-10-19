"""Founder registry includes organizations beyond the first API page."""
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from app.routers import billing


def test_registry_exposes_next_page_and_scopes_profiles(monkeypatch):
    orgs = [{"id": str(i), "name": f"Organization {i}"} for i in range(201)]
    tables = {name: MagicMock() for name in ["organizations", "org_commercial_profiles", "org_promotional_grants"]}
    tables["organizations"].select.return_value.order.return_value.order.return_value.range.return_value.execute.return_value.data = orgs
    tables["org_commercial_profiles"].select.return_value.in_.return_value.execute.return_value.data = []
    tables["org_promotional_grants"].select.return_value.in_.return_value.order.return_value.range.return_value.execute.return_value.data = []
    client = MagicMock()
    client.table.side_effect = tables.__getitem__
    monkeypatch.setattr(billing, "shared_service_client", lambda *_args: client)
    result = billing.list_commercial_accounts({}, MagicMock(commercial_offers_enabled=False), offset=0, limit=200)
    assert len(result["accounts"]) == 200
    assert result["has_more"] is True
    assert result["next_offset"] == 200
    assert result["accounts"][-1]["org_id"] == "199"
    assert tables["org_commercial_profiles"].select.return_value.in_.call_args.args == ("org_id", [str(i) for i in range(200)])


@pytest.mark.parametrize("offset,limit", [(-1,200),(0,0),(0,201)])
def test_invalid_registry_page_denied(offset,limit):
    with pytest.raises(HTTPException) as exc:
        billing.list_commercial_accounts({}, MagicMock(), offset=offset, limit=limit)
    assert exc.value.status_code == 422
