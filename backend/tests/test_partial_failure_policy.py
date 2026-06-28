"""Tests for partial-failure policy (STA-287)."""
from app.workflows.constants import (
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_PARTIAL_SUCCESS,
)
from app.workflows.partial_failure_policy import (
    FailureContext,
    POLICY_COMPENSATE,
    POLICY_FAIL_FAST,
    POLICY_PARTIAL_SUCCESS,
    resolve_failure_policy,
    resolve_run_status,
    summarize_partial_result,
)


def test_graph_parallel_is_fail_fast():
    assert resolve_failure_policy(FailureContext.WORKFLOW_GRAPH_PARALLEL) == POLICY_FAIL_FAST


def test_autonomous_chain_is_compensate():
    assert resolve_failure_policy(FailureContext.AUTONOMOUS_CONNECTOR_CHAIN) == POLICY_COMPENSATE


def test_department_pack_is_partial_success():
    assert resolve_failure_policy(FailureContext.DEPARTMENT_PACK_INSTALL) == POLICY_PARTIAL_SUCCESS


def test_all_success_returns_completed():
    assert (
        resolve_run_status(FailureContext.WORKFLOW_GRAPH, completed_count=3, failed_count=0)
        == RUN_STATUS_COMPLETED
    )


def test_partial_install_status():
    assert (
        resolve_run_status(
            FailureContext.DEPARTMENT_PACK_INSTALL,
            completed_count=2,
            failed_count=1,
            total_count=3,
        )
        == RUN_STATUS_PARTIAL_SUCCESS
    )


def test_graph_failure_is_failed_not_partial():
    assert (
        resolve_run_status(
            FailureContext.WORKFLOW_GRAPH_PARALLEL,
            completed_count=1,
            failed_count=1,
            total_count=2,
        )
        == RUN_STATUS_FAILED
    )


def test_compensate_context_still_failed_run_status():
    assert (
        resolve_run_status(
            FailureContext.AUTONOMOUS_CONNECTOR_CHAIN,
            completed_count=2,
            failed_count=1,
        )
        == RUN_STATUS_FAILED
    )


def test_summarize_partial_result_shape():
    payload = summarize_partial_result(
        completed=["a", "b"],
        failures=[{"item": "c", "error": "boom"}],
    )
    assert payload["status"] == RUN_STATUS_PARTIAL_SUCCESS
    assert payload["completedCount"] == 2
    assert payload["failedCount"] == 1
    assert payload["partialSuccess"] is True
