from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.services.msp_delegation_policy import AccessTier, Delegation
from app.services.msp_delegation_preflight import delegation_preflight


class Query:
    def __init__(self, db, table):
        self.db, self.table, self.filters = db, table, {}
    def select(self, *_): return self
    def eq(self, key, value):
        self.filters[key] = value
        return self
    def limit(self, *_): return self
    def execute(self):
        rows = self.db.records.get(self.table, [])
        return SimpleNamespace(data=[
            row for row in rows if all(row.get(k) == v for k, v in self.filters.items())
        ])


class DB:
    def __init__(self):
        self.records = {
            "organization_members": [
                {"org_id": "provider", "user_id": "tech", "role": "member"},
                {"org_id": "customer", "user_id": "owner", "role": "owner"},
            ],
            "organizations": [{"id": "customer", "parent_org_id": "provider"}],
        }
    def table(self, name): return Query(self, name)


def delegation():
    return Delegation(
        provider_org_id="provider", customer_org_id="customer",
        grantee_user_id="tech", tier=AccessTier.OVERVIEW,
        actions=frozenset({"account.health.read"}),
        approved_by_customer_user_id="owner",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


def allowed(db, grant=None):
    return delegation_preflight(
        db, grant or delegation(), provider_org_id="provider",
        customer_org_id="customer", user_id="tech", action="account.health.read",
    )


def test_live_membership_and_customer_owner_allow_preflight_only():
    assert allowed(DB())


def test_removed_provider_membership_deny():
    db = DB()
    db.records["organization_members"] = db.records["organization_members"][1:]
    assert not allowed(db)


def test_customer_owner_demoted_deny():
    db = DB()
    db.records["organization_members"][1]["role"] = "admin"
    assert not allowed(db)


def test_revoked_parent_relationship_deny():
    db = DB()
    db.records["organizations"][0]["parent_org_id"] = "other-provider"
    assert not allowed(db)


def test_database_lookup_failure_denies():
    db = DB()
    with patch.object(db, "table", side_effect=RuntimeError("db offline")):
        assert not allowed(db)


def test_no_grant_denies():
    assert not delegation_preflight(DB(), None, provider_org_id="provider", customer_org_id="customer", user_id="tech", action="account.health.read")


def test_cross_customer_replay_denied_even_with_valid_provider_membership():
    db = DB()
    db.records["organization_members"].append(
        {"org_id": "customer-b", "user_id": "owner-b", "role": "owner"}
    )
    db.records["organizations"].append(
        {"id": "customer-b", "parent_org_id": "provider"}
    )
    assert not delegation_preflight(
        db, delegation(), provider_org_id="provider",
        customer_org_id="customer-b", user_id="tech",
        action="account.health.read",
    )


def test_cross_provider_replay_denied_even_when_customer_link_changes():
    db = DB()
    db.records["organization_members"].append(
        {"org_id": "other-provider", "user_id": "tech", "role": "member"}
    )
    db.records["organizations"][0]["parent_org_id"] = "other-provider"
    assert not delegation_preflight(
        db, delegation(), provider_org_id="other-provider",
        customer_org_id="customer", user_id="tech",
        action="account.health.read",
    )


def test_removed_customer_owner_cannot_keep_existing_delegation_active():
    db = DB()
    db.records["organization_members"] = [
        row for row in db.records["organization_members"]
        if row["user_id"] != "owner"
    ]
    assert not allowed(db)



def test_mismatched_membership_rows_never_authorize_even_if_filters_fail():
    class UnfilteredDB(DB):
        def table(self, name):
            query = super().table(name)
            if name == "organization_members":
                def unfiltered_execute():
                    return SimpleNamespace(data=[{"org_id": "wrong-org", "user_id": "tech", "role": "owner"}])
                query.execute = unfiltered_execute
            return query

    assert not allowed(UnfilteredDB())


def test_duplicate_membership_rows_fail_closed():
    db = DB()
    db.records["organization_members"].append(
        {"org_id": "provider", "user_id": "tech", "role": "owner"}
    )
    assert not allowed(db)
