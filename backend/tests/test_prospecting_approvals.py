from unittest.mock import MagicMock
from app.plays.prospecting_approvals import payload_digest,resolve_stage_approval

def test_canonical_digest_independent_of_key_order():
    assert payload_digest({"a":1,"b":2})==payload_digest({"b":2,"a":1})

def test_rpc_denial_cannot_authorize():
    client=MagicMock()
    client.rpc.return_value.execute.return_value.data=False
    assert not resolve_stage_approval(client,org_id="o",run_id="r",stage="outreach_enroll",
        actor_id="u",approved_payload={"campaign":"c","to":"test@example.ca"})
    assert client.rpc.call_args.args[0]=="prospect_stage_approval_verified"

def test_rpc_unavailable_fails_closed():
    client=MagicMock()
    client.rpc.side_effect=RuntimeError("offline")
    assert not resolve_stage_approval(client,org_id="o",run_id="r",stage="crm_export",
        actor_id="u",approved_payload={})
