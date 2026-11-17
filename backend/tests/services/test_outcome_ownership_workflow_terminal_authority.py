"""Workflow callers must expose acknowledged canonical truth, never step intent."""
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from app.services.execution_outcome import require_workflow_terminal_outcome
from tests.services.outcome_rpc_fake import unit_finalization_result


def result(status="completed", **fanout):
    value = unit_finalization_result(None, status=status, run_id="run-1")
    value.fanout.update(fanout)
    return value


@pytest.mark.parametrize("status", ["completed", "cancelled", "failed", "partial_success", "verification_inconclusive"])
def test_acknowledged_workflow_status_is_authoritative(status):
    assert require_workflow_terminal_outcome(None, result(status), run_id="run-1") == status


@pytest.mark.parametrize("bad", [
    None,
    replace(result(), run_id="another-run"),
    replace(result(), status="running"),
    replace(result(), fanout=None),
    result(run_persisted=False),
    result(persistence_failed=True),
])
def test_missing_or_failed_terminal_acknowledgement_cannot_be_reported_as_success(bad):
    with pytest.raises(RuntimeError):
        require_workflow_terminal_outcome(None, bad, run_id="run-1")


@pytest.mark.parametrize("refreshed", [True, False])
def test_conflicting_terminal_refreshes_only_current_canonical_projection(refreshed):
    client = MagicMock()
    conflict = result("cancelled", terminal_conflict=True)
    with patch("app.workflows.schema_sync.mirror_legacy_run_to_contract", return_value=refreshed) as refresh:
        if refreshed:
            assert require_workflow_terminal_outcome(client, conflict, run_id="run-1") == "cancelled"
        else:
            with pytest.raises(RuntimeError, match="projection refresh failed"):
                require_workflow_terminal_outcome(client, conflict, run_id="run-1")
    refresh.assert_called_once_with(client, "run-1")
