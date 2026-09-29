from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_play_observe_routes_do_not_own_execution():
    source = (ROOT / "app" / "routers" / "plays.py").read_text()
    forbidden = (
        "execute_workflow_steps(",
        "invoke_tool(",
        "execute_write_action(",
        "create_execute_run(",
    )
    for token in forbidden:
        assert token not in source


def test_play_workflow_binding_mutations_require_admin():
    source = (ROOT / "app" / "routers" / "plays.py").read_text()
    assert 'Depends(require_admin)' in source
    assert 'action="play.workflow.bound"' in source
    assert 'action="play.workflow.unbound"' in source


def test_execution_bridge_can_only_emit_actioned_business_state():
    source = (ROOT / "app" / "services" / "execution_outcome.py").read_text()
    start = source.index("def _record_play_actioned_result")
    end = source.index("def _coerce_verified_output", start)
    bridge = source[start:end]
    assert "BusinessResultStatus.ACTIONED" in bridge
    assert "BusinessResultStatus.VERIFIED_SUCCESS" not in bridge
    assert "provider_acceptance_is_business_verification" in bridge


def test_play_dataset_binding_table_is_tenant_scoped_with_rls():
    migration = (
        ROOT.parent
        / "supabase"
        / "migrations"
        / "20260929134000_training_dataset_bindings.sql"
    ).read_text()
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "organization_members" in migration
    assert "org_id" in migration


def test_play_business_result_contract_requires_source_of_record_for_verified_success():
    source = (ROOT / "app" / "plays" / "outcomes.py").read_text()
    assert "VERIFIED SUCCESS requires at least one source-of-record reference" in source
    assert "verified business results require verification_method" in source
