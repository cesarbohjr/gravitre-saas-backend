from unittest.mock import MagicMock, patch

from app.services.chat_connector_execution_service import ChatConnectorExecutionService, ConnectorActionPlan
from app.services.conversational_execution_service import ExecutionResult
from app.services.post_action_experience_service import build_post_action_recommendation, what_this_means


def _plan():
    return ConnectorActionPlan(tool_name="hubspot_contacts_create", invoke_action="hubspot.contacts.create", integration="hubspot", kind="write", label="Create contact", args={"properties":{"email":"a@b.co"}}, requires_approval=True)


def _result():
    return ExecutionResult(success=True, entity_type="contact", entity_id="123", title="Created", body="Created.", integration="hubspot", task_label="Create contact", structured={})


def test_followup_verified_write_is_not_presented_as_terminal_success():
    service=ChatConnectorExecutionService()
    result=_result()
    ctx=MagicMock(); ctx.connector_id="conn-1"; ctx.environment_name="production"
    with patch("app.workflows.repository.create_run", return_value={"id":"run-1"}), patch("app.workflows.repository.create_step", return_value={"id":"step-1"}), patch("app.workflows.repository.update_step"), patch("app.services.execution_outcome.finalize_execution_outcome"), patch("app.services.write_success_verification.schedule_write_success_verification"):
        service._finalize_connector_outcome(MagicMock(), org_id="org-1", user_id="user-1", conversation_id="conv-1", plan=_plan(), result=result, tool_ctx=ctx, connector_id="conn-1")
    verification=result.structured["verification"]
    assert verification["state"]=="verifying"
    assert verification["verified"] is False
    assert result.structured["canonical_lifecycle"]=="EXECUTED_UNVERIFIED"
    assert result.structured["execution_verified"] is False
    assert "verifying" in result.body.lower()


def test_pending_verification_suppresses_completion_consequence_and_next_action():
    result=_result()
    result.structured={"verification":{"required":True,"verified":False,"state":"verifying"}}
    assert "before I call it complete" in what_this_means(plan=_plan(), result=result)
    assert build_post_action_recommendation(plan=_plan(), result=result) is None
