from app.plays.contracts import PlayMaturity
from app.plays.installations import PlayInstallation, PlayRun, canonical_workflow_run_parameters


def test_installation_serializes_operating_mode_without_execution_authority_drift():
    installation = PlayInstallation(
        id="install-1",
        org_id="org-1",
        play_key="customer-rescue",
        play_version="1",
        environment_name="production",
        operating_mode=PlayMaturity.ACT_WITH_APPROVAL,
        status="ready",
        goal_id="goal-1",
    )
    payload = installation.as_dict()
    assert payload["operating_mode"] == "ACT WITH APPROVAL"
    assert payload["goal_id"] == "goal-1"


def test_play_run_groups_canonical_workflow_runs():
    run = PlayRun(
        id="play-run-1",
        org_id="org-1",
        installation_id="install-1",
        play_key="customer-rescue",
        play_version="1",
        operating_mode=PlayMaturity.OBSERVE,
        trigger_type="manual",
        status="running",
        workflow_run_ids=("workflow-run-1", "workflow-run-2"),
    )
    assert run.as_dict()["workflow_run_ids"] == ("workflow-run-1", "workflow-run-2")


def test_workflow_parameters_preserve_canonical_runtime_as_only_execution_authority():
    installation = PlayInstallation(
        id="install-1",
        org_id="org-1",
        play_key="revenue-recovery",
        play_version="1",
        environment_name="production",
        operating_mode=PlayMaturity.ACT_WITH_APPROVAL,
        status="ready",
    )
    params = canonical_workflow_run_parameters(installation, play_run_id="play-run-1")
    assert params == {
        "play": {
            "key": "revenue-recovery",
            "version": "1",
            "installation_id": "install-1",
            "run_id": "play-run-1",
            "operating_mode": "ACT WITH APPROVAL",
            "execution_authority": "canonical_workflow_runtime",
        }
    }
