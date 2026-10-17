from datetime import datetime, timedelta, timezone

from app.services.msp_delegation_policy import AccessTier, Delegation, is_allowed


NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


def grant(tier=AccessTier.OVERVIEW, **changes):
    fields = dict(
        provider_org_id="msp-1",
        customer_org_id="customer-a",
        grantee_user_id="tech-1",
        tier=tier,
        actions=frozenset({"account.health.read", "agent.configure", "document.read"}),
        approved_by_customer_user_id="customer-owner",
        expires_at=NOW + timedelta(hours=1),
    )
    fields.update(changes)
    return Delegation(**fields)


def check(g, action="account.health.read", **changes):
    fields = dict(provider_org_id="msp-1", customer_org_id="customer-a", user_id="tech-1", action=action, now=NOW)
    fields.update(changes)
    return is_allowed(g, **fields)


def test_no_grant_and_unrecognized_action_deny():
    assert not check(None)
    assert not check(grant(), "unknown.action")


def test_tiers_limit_effective_actions_even_if_grant_contains_more():
    assert check(grant(), "account.health.read")
    assert not check(grant(), "agent.configure")
    assert not check(grant(), "document.read")
    assert check(grant(AccessTier.ADMINISTRATION), "agent.configure")
    assert not check(grant(AccessTier.ADMINISTRATION), "document.read")
    assert check(grant(AccessTier.SENSITIVE), "document.read")


def test_cross_tenant_cross_provider_and_other_user_deny():
    assert not check(grant(), customer_org_id="customer-b")
    assert not check(grant(), provider_org_id="msp-2")
    assert not check(grant(), user_id="tech-2")
    assert not check(grant(customer_org_id="msp-1"), customer_org_id="msp-1")


def test_expired_revoked_and_missing_customer_consent_deny():
    assert not check(grant(expires_at=NOW))
    assert not check(grant(revoked_at=NOW - timedelta(minutes=1)))
    assert not check(grant(approved_by_customer_user_id=""))
    assert not check(grant(expires_at=datetime(2026, 10, 18)))


def test_explicit_action_allowlist_required():
    assert not check(grant(AccessTier.SENSITIVE, actions=frozenset()), "document.read")
