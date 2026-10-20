"""Partner org names only show where the viewer is entitled to see them."""
from __future__ import annotations

from types import SimpleNamespace

from app.routers import federation as federation_router

ME = "aaaaaaaa-0000-0000-0000-000000000000"


class _Orgs:
    def __init__(self):
        self.requested: list[str] = []

    def table(self, name):
        assert name == "organizations"
        return self

    def select(self, *_a):
        return self

    def in_(self, _key, ids):
        self.requested = list(ids)
        return self

    def execute(self):
        names = {"p-active": "Acme", "p-invited-us": "Globex", "p-we-invited": "Initech"}
        return SimpleNamespace(data=[{"id": i, "name": names[i]} for i in self.requested if i in names])


def test_partner_names_visible_for_active_and_inbound_invites_only():
    client = _Orgs()
    rows = [
        {"id": "1", "partnerOrgId": "p-active", "invitedByOrgId": ME, "status": "active"},
        {"id": "2", "partnerOrgId": "p-invited-us", "invitedByOrgId": "p-invited-us", "status": "pending_partner"},
        {"id": "3", "partnerOrgId": "p-we-invited", "invitedByOrgId": ME, "status": "pending_partner"},
    ]
    out = {r["id"]: r for r in federation_router._with_partner_names(client, ME, rows)}
    assert out["1"]["partnerOrgName"] == "Acme"
    assert out["2"]["partnerOrgName"] == "Globex"
    assert out["3"]["partnerOrgName"] is None
    assert "p-we-invited" not in client.requested


def test_partner_names_lookup_failure_keeps_partnerships():
    class _Broken:
        def table(self, _name):
            raise RuntimeError("db down")

    rows = [{"id": "1", "partnerOrgId": "p", "invitedByOrgId": ME, "status": "active"}]
    out = federation_router._with_partner_names(_Broken(), ME, rows)
    assert out[0]["partnerOrgName"] is None
    assert out[0]["id"] == "1"
