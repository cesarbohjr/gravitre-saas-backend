"""Post-action language must not promote an accepted but unverified provider write."""
from types import SimpleNamespace
import pytest
from app.services.post_action_experience_service import what_this_means, build_post_action_recommendation

@pytest.mark.parametrize("verified", [False, None])
def test_unverified_write_suppresses_success_consequences(verified):
    plan = SimpleNamespace(kind="write", invoke_action="gmail.messages.send", integration="gmail")
    result = SimpleNamespace(success=True, title="Sent", body="Sent", integration="gmail",
                             entity_id="item1", external_url=None, result_url=None,
                             structured={"verification": {"required": True, "verified": verified}})
    assert "pending" in what_this_means(plan=plan, result=result).lower()
    assert build_post_action_recommendation(plan=plan, result=result) is None


def test_verified_write_can_show_post_action_consequence():
    plan = SimpleNamespace(kind="write", invoke_action="gmail.messages.send", integration="gmail")
    result = SimpleNamespace(success=True, title="Sent", body="Sent", integration="gmail",
                             entity_id="item1", external_url=None, result_url=None,
                             structured={"verification": {"required": True, "verified": True}})
    assert "Sent folder" in what_this_means(plan=plan, result=result)
