from unittest.mock import MagicMock
from app.plays.prospecting_execution import run_stage

def test_atomic_finish_advances_only_on_database_confirmation():
    db=MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[
      {"id":"run-1","state":"running","current_stage":"discover"}]
    db.rpc.return_value.execute.return_value.data=True
    result=run_stage(db,org_id="tenant",run_id="run-1",stage="discover",actor_id="actor",execute=lambda:{"success":True})
    assert result["next_stage"]=="research"
    rpc_names=[call.args[0] for call in db.rpc.call_args_list]
    assert rpc_names==["prospect_claim_step","prospect_finish_step"]
    assert db.rpc.call_args.args[1]["p_next"]=="research"

def test_atomic_finish_failure_is_not_success():
    db=MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[
      {"id":"run-1","state":"running","current_stage":"discover"}]
    db.rpc.side_effect=None
    db.rpc.return_value.execute.side_effect=[MagicMock(data=True),MagicMock(data=False)]
    import pytest
    with pytest.raises(RuntimeError,match="Atomic stage finalization failed"):
        run_stage(db,org_id="tenant",run_id="run-1",stage="discover",actor_id="actor",execute=lambda:{"success":True})
