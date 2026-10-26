from unittest.mock import MagicMock
from app.plays.prospecting_execution import run_stage

def test_second_worker_cannot_execute_after_claim_lost():
    client=MagicMock()
    query=client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value
    query.data=[{"id":"run-1","state":"running","current_stage":"discover"}]
    client.rpc.return_value.execute.return_value.data=False
    called=[]
    result=run_stage(client,org_id="tenant",run_id="run-1",stage="discover",actor_id="actor",
        execute=lambda:called.append(1) or {"success":True})
    assert result["status"]=="concurrent_or_invalid_claim"
    assert not called
    assert client.rpc.call_args.args[0]=="prospect_claim_step"
