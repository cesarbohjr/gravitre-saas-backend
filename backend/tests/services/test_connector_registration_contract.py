"""Registration contract tests — allowlist shrink tracker for connector governance debt."""
from __future__ import annotations

from app.services.connector_allowlists import (
    API_IMPORT_EXCEPTION_ALLOWLIST,
    ORPHAN_HANDLER_ALLOWLIST,
    PENDING_WORKFLOW_SCHEMA_ALLOWLIST,
)
from app.services.connector_registration_contract import (
    CONNECTOR_GOVERNANCE_PYTEST_TARGETS,
    assert_registration_contract,
    collect_api_import_exceptions,
    collect_migrated_workflow_schema_gaps,
    collect_orphan_handlers,
    collect_pending_workflow_schemas,
    registration_contract_summary,
    verify_registration_contract,
)


def test_orphan_handler_allowlist_matches_actual_debt():
    actual = collect_orphan_handlers()
    assert actual == ORPHAN_HANDLER_ALLOWLIST, (
        f"orphan mismatch stale={sorted(ORPHAN_HANDLER_ALLOWLIST - actual)} "
        f"unmanaged={sorted(actual - ORPHAN_HANDLER_ALLOWLIST)}"
    )


def test_api_import_exception_allowlist_matches_actual_debt():
    actual = collect_api_import_exceptions()
    assert actual == API_IMPORT_EXCEPTION_ALLOWLIST, (
        f"api import mismatch stale={sorted(API_IMPORT_EXCEPTION_ALLOWLIST - actual)} "
        f"unmanaged={sorted(actual - API_IMPORT_EXCEPTION_ALLOWLIST)}"
    )


def test_pending_workflow_schema_allowlist_matches_actual_debt():
    actual = collect_pending_workflow_schemas()
    assert actual == PENDING_WORKFLOW_SCHEMA_ALLOWLIST, (
        f"pending_schema mismatch stale={sorted(PENDING_WORKFLOW_SCHEMA_ALLOWLIST - actual)} "
        f"unmanaged={sorted(actual - PENDING_WORKFLOW_SCHEMA_ALLOWLIST)}"
    )


def test_all_allowlist_buckets_exact_match():
    buckets = verify_registration_contract()
    assert all(bucket.is_exact_match for bucket in buckets)


def test_step1_registration_contract_enforcement():
    assert_registration_contract()


def test_migrated_workflow_schema_gaps_empty_until_step3():
    gaps = collect_migrated_workflow_schema_gaps()
    assert gaps == frozenset()
    assert "hubspot.contacts.create" not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST
    assert "slack.post_message" not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_registration_contract_summary_shape():
    summary = registration_contract_summary()
    assert summary["orphanHandlersRemaining"] == len(ORPHAN_HANDLER_ALLOWLIST)
    assert summary["apiImportExceptionsRemaining"] == len(API_IMPORT_EXCEPTION_ALLOWLIST)
    assert summary["pendingWorkflowSchemaRemaining"] == len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST)
    assert summary["allExactMatches"] is True
    assert summary["migratedWorkflowSchemaGaps"] == []


def test_allowlist_sizes_are_explicit_backlog():
    assert len(ORPHAN_HANDLER_ALLOWLIST) == 0
    assert len(API_IMPORT_EXCEPTION_ALLOWLIST) == 0
    assert len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST) == 43


def test_connector_governance_pytest_targets_cover_core_suites():
    joined = " ".join(CONNECTOR_GOVERNANCE_PYTEST_TARGETS)
    assert "test_connector_action_workflows.py" in joined
    assert "test_connector_parameter_inference.py" in joined
    assert "test_action_workflow_validation.py" in joined
    assert "test_connector_registration_contract.py" in joined


def test_step3_enforcement_flags_pass_when_migrated_gaps_empty():
    assert_registration_contract(
        enforce_pending_workflow_schema=True,
        enforce_migrated_workflow_schemas=True,
    )
