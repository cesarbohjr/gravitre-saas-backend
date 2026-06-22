from app.services.execution_mode_service import resolve_execution_mode, resolve_execution_verified


def test_execution_mode_tools_executed():
    mode = resolve_execution_mode(
        react_status="completed",
        tool_calls=[{"tool": "hubspot_search_contacts", "result": {"success": True}}],
    )
    assert mode == "tools_executed"


def test_execution_mode_advisory_only():
    mode = resolve_execution_mode(react_status="completed", tool_calls=[])
    assert mode == "advisory_only"


def test_execution_mode_degraded_on_error():
    mode = resolve_execution_mode(
        react_status="completed",
        tool_calls=[],
        error="AI disabled",
    )
    assert mode == "degraded"


def test_execution_verified_requires_successful_tool():
    assert resolve_execution_verified(tools_available=2, tool_calls=[]) is False
    assert (
        resolve_execution_verified(
            tools_available=2,
            tool_calls=[{"result": {"success": True}}],
        )
        is True
    )
    assert resolve_execution_verified(tools_available=0, tool_calls=[{"result": {"success": True}}]) is False
