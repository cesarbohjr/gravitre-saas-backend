"""Capabilities fall back across providers on refusals, and planning routes around blocked providers."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.outcome_packs.memory_store import MemoryStore
from app.services import capability_availability as ca
from app.services.tool_types import NormalizedResult, ToolAuthExpiredError, ToolOutcomeUncertainError, ToolValidationError

ORG = "00000000-0000-4000-8000-0000000000b2"


def _ctx(store):
    return SimpleNamespace(client=store, org_id=ORG, settings=None)


def test_classify_failure():
    assert ca.classify_failure(ToolAuthExpiredError("x")) == "auth_expired"
    assert ca.classify_failure(NormalizedResult(success=False, action="a", error_message="402 Payment Required: upgrade your plan")) == "plan_limit"
    assert ca.classify_failure(NormalizedResult(success=False, action="a", error_message="429 Too Many Requests")) == "rate_limited"
    assert ca.classify_failure(ToolOutcomeUncertainError("timed out")) is None


def test_falls_back_to_next_provider_and_records_refusal():
    store = MemoryStore()
    calls = []

    def invoke(ctx, action, params):
        calls.append(action)
        if action.startswith("apollo."):
            return NormalizedResult(success=False, action=action, error_message="Insufficient credits on your plan")
        return NormalizedResult(success=True, action=action, data={"people": []})

    result = ca.invoke_capability_with_fallback(
        _ctx(store), "capability.prospect.discovery",
        {"_connected_integrations": ["apollo", "pdl"], "_capability_fallback": True}, invoke=invoke,
    )
    assert result.success and not result.action.startswith("apollo.")
    assert calls[0].startswith("apollo.") and len(calls) == 2
    assert result.data["capability_fallback"]["skipped"][0]["state"] == "plan_limit"
    blocks = ca.load_blocks(store, ORG)
    # A plan limit is an entitlement on the refused action, not on the vendor:
    # Apollo enrichment can still run while Apollo people search cannot.
    assert blocks and blocks[0].vendor == "apollo" and blocks[0].action == "apollo.people.search"
    usable, _ = ca.ordered_alternatives("prospect.enrichment", connected=["apollo"], blocks=blocks)
    assert usable and usable[0][0] == "apollo"

    # The next call routes around the blocked provider without trying it.
    calls.clear()
    ca.invoke_capability_with_fallback(
        _ctx(store), "capability.prospect.discovery",
        {"_connected_integrations": ["apollo", "pdl"], "_capability_fallback": True}, invoke=invoke,
    )
    assert not any(c.startswith("apollo.") for c in calls)


def test_uncertain_write_never_falls_back():
    store = MemoryStore()

    def invoke(ctx, action, params):
        raise ToolOutcomeUncertainError("connection reset after send")

    with pytest.raises(ToolOutcomeUncertainError):
        ca.invoke_capability_with_fallback(
            _ctx(store), "capability.crm.deal.create",
            {"_connected_integrations": ["hubspot", "salesforce"], "_capability_fallback": True}, invoke=invoke,
        )
    assert ca.load_blocks(store, ORG) == []


def test_ambiguity_without_opt_in_still_asks():
    with pytest.raises(ToolValidationError) as exc:
        ca.invoke_capability_with_fallback(
            _ctx(MemoryStore()), "capability.crm.deal.create",
            {"_connected_integrations": ["hubspot", "salesforce"]}, invoke=lambda *a: None,
        )
    assert exc.value.code == "CAPABILITY_AMBIGUOUS"


def test_expired_block_is_ignored():
    store = MemoryStore()
    ca.record_unavailable(store, ORG, action="apollo.people.search", state="unhealthy")
    from datetime import datetime, timedelta, timezone

    assert ca.load_blocks(store, ORG)
    assert ca.load_blocks(store, ORG, now=datetime.now(timezone.utc) + timedelta(hours=2)) == []
