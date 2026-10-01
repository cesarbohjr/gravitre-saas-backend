from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYS = (ROOT / "app" / "routers" / "plays.py").read_text()
WORKFLOWS = (ROOT / "app" / "routers" / "workflows.py").read_text()


def test_play_run_delegates_to_canonical_workflow_execute():
    assert "await execute_workflow(" in PLAYS
    assert '"execution_authority": "canonical_workflow_runtime"' in PLAYS
    assert "connector" not in PLAYS[PLAYS.index("async def run_play"):PLAYS.index('@router.get("/{play_key}/workflow-bindings")].lower().replace("connected_vendors", "")


def test_act_with_approval_preflights_every_bound_workflow():
    block = PLAYS[PLAYS.index("async def run_play"):PLAYS.index('@router.get("/{play_key}/workflow-bindings")']
    assert 'resolve_policy(client, org_id, workflow_id, "execute")' in block
    assert "required_approvals < 1" in block
    assert "Preflight every workflow before starting any of them" in block


def test_act_within_policy_fails_closed_until_effective_authorization_exists():
    block = PLAYS[PLAYS.index("async def run_play"):PLAYS.index('@router.get("/{play_key}/workflow-bindings")']
    assert 'if mode == "ACT WITHIN POLICY"' in block
    assert "effective runtime action authorization" in block


def test_workflow_run_preserves_play_trace_identity():
    assert '"installation_id"' not in WORKFLOWS or "**requested_play" in WORKFLOWS
    assert "**requested_play" in WORKFLOWS
    assert '"execution_authority": "canonical_workflow_runtime"' in WORKFLOWS
