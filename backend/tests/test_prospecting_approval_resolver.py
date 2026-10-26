from unittest.mock import MagicMock
from app.plays.prospecting_execution import run_stage

def mock_client():
    client=MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[
        {"id":"run-1","state":"running","current_stage":"outreach_enroll"}]
    return client

def test_outreach_does_not_execute_without_authoritative_pending_action():
    db=mock_client()
    did_run=[]
    result=run_stage(db,org_id="org-1",run_id="run-1",stage="outreach_enroll",
        actor_id="actor-1",execute=lambda:did_run.append(True) or {"success":True})
    assert result["status"]=="awaiting_approval"
    assert not did_run

def test_fake_or_cross_tenant_approval_is_rejected():
    db=mock_client()
    did_run=[]
    def resolver(org,actor,run,stage):
        assert (org,actor,run,stage)==("org-1","actor-1","run-1","outreach_enroll")
        return False
    result=run_stage(db,org_id="org-1",run_id="run-1",stage="outreach_enroll",
        actor_id="actor-1",execute=lambda:did_run.append(True) or {"success":True},
        approval_resolver=resolver)
    assert result["status"]=="awaiting_approval"
    assert not did_run
