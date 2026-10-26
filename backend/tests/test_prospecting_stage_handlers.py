from unittest.mock import MagicMock
from app.plays.prospecting_stage_handlers import _handle, ACTIONS
from app.marketplace.workflows.qualified_prospecting_workflow import STAGE_ACTIONS

def context():
    ctx=MagicMock()
    ctx.org_id="org-a"
    ctx.actor_id="user-a"
    return ctx

def test_all_native_stages_declared():
    for key in ("discover","research","verify","consent_review","stage"):
        assert STAGE_ACTIONS[key].split("prospecting.",1)[1] in ACTIONS

def test_review_and_staging_cannot_be_automated():
    ctx=context()
    review=_handle(ctx,"contacts.review",{})
    stage=_handle(ctx,"contacts.stage",{"approved_pending_action_id":"unverified"})
    assert not review.success
    assert not stage.success
    assert review.error_code=="permission_denied"
    assert stage.error_code=="permission_denied"

def test_discovery_cannot_cross_tenant():
    ctx=context()
    ctx.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
    response=_handle(ctx,"companies.discover",{})
    assert response.success
    assert response.data["companies"]==[]
    assert ctx.client.table.return_value.select.return_value.eq.call_args_list[0].args==("org_id","org-a")

def test_stage_does_not_write_even_when_supplied_fake_approval():
    ctx=context()
    _handle(ctx,"contacts.stage",{"approved_pending_action_id":"fake"})
    ctx.client.table.assert_not_called()
