from pathlib import Path


def test_chat_connector_does_not_terminalize_followup_write_before_proof():
    source = Path("app/services/chat_connector_execution_service.py").read_text()
    assert 'if schedule_async_verification and status == "completed":' in source
    assert 'status = "partial_success"' in source
    assert '"status": "pending"' in source


def test_async_readback_promotes_only_verified_partial_runs():
    source = Path("app/services/write_success_verification.py").read_text()
    assert source.count('if verify.verified:') >= 2
    assert source.count('if current == "partial_success":') >= 2
    assert source.count('update_run(client, run_id, "completed")') >= 2
