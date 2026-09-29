from app.services.computer_execution import classify_execution_strategy, observation_from_browser_result
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep


def test_api_native_when_action_spec_exists() -> None:
    assert classify_execution_strategy(invoke_action="hubspot.contacts.create", has_action_spec=True) == "api_native"
    assert classify_execution_strategy(requires_graphical_ui=True) == "browser_cdp"
    assert (
        classify_execution_strategy(invoke_action="hubspot.contacts.create", requires_graphical_ui=True)
        == "hybrid"
    )


def test_browser_observation_is_canonical() -> None:
    plan = ExecutionPlan(
        plan_id="p1",
        summary="read",
        source="computer_execution",
        steps=[ExecutionStep(step_id="computer_primary", title="read", kind="read")],
    )
    obs = observation_from_browser_result(
        plan=plan,
        result={"success": True, "url": "https://example.com", "text": "hello", "mode": "httpx_read"},
        approval_id="appr-1",
    )
    assert obs.success is True
    assert obs.structured["url"] == "https://example.com"
    assert obs.structured["approval_id"] == "appr-1"
    assert obs.structured["strategy"] == "browser_cdp"
    assert obs.plan_id == "p1"
