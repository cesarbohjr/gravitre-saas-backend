"""Seven-intelligence prompt envelope regression for all specialist roles."""
import pytest

from app.services.intelligence_router import CAPABILITY_NAMES, intelligence_context_block


@pytest.mark.parametrize("role", ("engineering", "qa", "security", "agency"))
def test_all_seven_evidence_slots_remain_visible_for_each_role(role):
    capabilities = {name: {"status": "available", "source": "fixture", "advisory_only": True}
                    for name in CAPABILITY_NAMES}
    block = intelligence_context_block({"capabilities": capabilities}, agent_role=role)
    assert "Role:" in block
    assert "grants no permissions or approval" in block
    for name in CAPABILITY_NAMES:
        assert f'"{name}"' in block
    assert "<intelligence_evidence>" in block


@pytest.mark.parametrize("role", ("engineering", "qa", "security", "agency"))
def test_unavailable_capabilities_are_not_claimed_active(role):
    capabilities = {name: {"status": "deferred", "advisory_only": True}
                    for name in CAPABILITY_NAMES}
    block = intelligence_context_block({"capabilities": capabilities}, agent_role=role)
    for name in CAPABILITY_NAMES:
        assert f'"{name}": {{"status": "deferred"' in block
    assert "grants no permissions or approval" in block


def test_unknown_role_does_not_receive_privileged_guidance():
    block = intelligence_context_block({"capabilities": {"contextual": {"status": "unavailable"}}},
                                       agent_role="superuser")
    assert "Role:" not in block
    assert '"contextual"' in block
