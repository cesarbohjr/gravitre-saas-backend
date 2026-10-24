"""MSP authorization regression: revocation, scope and tier are live per request."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.services.msp_delegated_access import authorize_live_action


PROVIDER = "provider-a"
CUSTOMER = "customer-a"
USER = "provider-user"


class Query:
    def __init__(self, store):
        self.store = store
        self.filters = {}
    def select(self, *_): return self
    def eq(self, key, value):
        self.filters[key] = value
        return self
    def is_(self, key, value):
        self.filters[key] = None
        return self
    def gt(self, *_): return self
    def execute(self):
        rows = [r for r in self.store if all(r.get(k) == v for k, v in self.filters.items())]
        return SimpleNamespace(data=rows)


class Client:
    def __init__(self, store): self.store = store
    def table(self, name):
        assert name == "msp_delegations"
        return Query(self.store)


def _grant(customer=CUSTOMER, actions=None, hours=1):
    return {
        "provider_org_id": PROVIDER,
        "customer_org_id": customer,
        "grantee_user_id": USER,
        "tier": 1,
        "actions": actions or ["account.health.read"],
        "approved_by_customer_user_id": "owner-a",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(),
        "revoked_at": None,
    }


def _check(db, customer=CUSTOMER, action="account.health.read"):
    return authorize_live_action(
        db, provider_org_id=PROVIDER, customer_org_id=customer,
        grantee_user_id=USER, action=action,
    )


def test_revoke_is_visible_to_existing_session_on_next_request():
    grant = _grant()
    db = Client([grant])
    with patch("app.services.msp_delegated_access.delegation_preflight", return_value=True):
        assert _check(db)
        grant["revoked_at"] = datetime.now(timezone.utc).isoformat()
        assert not _check(db)


def test_cross_customer_and_over_action_deny():
    db = Client([_grant()])
    with patch("app.services.msp_delegated_access.delegation_preflight", return_value=True):
        assert not _check(db, customer="customer-b")
    # The real tier/action preflight must never be bypassed for unsupported actions.
    from app.services.msp_delegation_policy import AccessTier, Delegation, is_allowed
    g = _grant()
    grant = Delegation(PROVIDER, CUSTOMER, USER, AccessTier.OVERVIEW,
                       frozenset(g["actions"]), "owner-a",
                       datetime.fromisoformat(g["expires_at"]))
    assert not is_allowed(grant, provider_org_id=PROVIDER,
        customer_org_id=CUSTOMER, user_id=USER, action="document.read",
        customer_approval_verified=True, provider_membership_verified=True,
        customer_relationship_verified=True)


def test_expired_and_storage_failure_deny():
    db = Client([_grant(hours=-1)])
    with patch("app.services.msp_delegated_access.delegation_preflight",
               side_effect=lambda _, grant, **kw: grant.expires_at > datetime.now(timezone.utc)):
        assert not _check(db)
    class Failed:
        def table(self, *_): raise RuntimeError("database unavailable")
    assert not _check(Failed())


class UnfilteredClient:
    """Simulates a broken PostgREST/query adapter returning unrelated rows."""
    def __init__(self, rows):
        self.rows = rows
    def table(self, name):
        assert name == "msp_delegations"
        return self
    def select(self, *_): return self
    def eq(self, *_): return self
    def is_(self, *_): return self
    def gt(self, *_): return self
    def execute(self): return SimpleNamespace(data=self.rows)


def test_unfiltered_database_response_never_grants_cross_tenant_access():
    rows = [_grant(customer="customer-b"), _grant()]
    with patch("app.services.msp_delegated_access.delegation_preflight", return_value=True) as check:
        assert not _check(UnfilteredClient(rows[:1]))
        assert _check(UnfilteredClient(rows))
        assert check.call_count == 1


def test_unfiltered_database_response_rejects_expired_revoked_and_wrong_user():
    expired = _grant(hours=-1)
    revoked = _grant()
    revoked["revoked_at"] = datetime.now(timezone.utc).isoformat()
    wrong_user = _grant()
    wrong_user["grantee_user_id"] = "other-provider-user"
    with patch("app.services.msp_delegated_access.delegation_preflight", return_value=True) as check:
        assert not _check(UnfilteredClient([expired, revoked, wrong_user]))
        check.assert_not_called()


def test_unfiltered_database_response_rejects_naive_expiry():
    row = _grant()
    row["expires_at"] = (datetime.now() + timedelta(hours=1)).isoformat()
    with patch("app.services.msp_delegated_access.delegation_preflight", return_value=True) as check:
        assert not _check(UnfilteredClient([row]))
        check.assert_not_called()
