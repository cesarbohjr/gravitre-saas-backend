"""ECO-003: ensure telemetry never logs tenant-specific context or request content."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "app/services/context_assembler.py"


def test_context_telemetry_contains_stage_durations_and_no_identifiers():
    tree = ast.parse(SOURCE.read_text())
    messages = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "info"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and node.args[0].value.startswith("eco003_context_stage_timing")
    ]
    assert len(messages) == 1
    message = messages[0]
    for field in ("retrieval_ms=", "company_ms=", "research_ms=", "total_ms=", "retrieval_ok=", "research_requested="):
        assert field in message
    for forbidden in ("org_id", "user_id", "request=", "query=", "email=", "context="):
        assert forbidden not in message


def test_context_telemetry_preserves_existing_sequential_awaits():
    source = SOURCE.read_text()
    assert "await get_unified_retrieval_service().retrieve(" in source
    assert "await get_company_intelligence_orchestrator().get_context_for_prompt(org_id)" in source
    assert "await get_research_service(self.settings).research(" in source


def test_retrieval_failure_logging_does_not_expose_tenant_or_exception_message():
    tree = ast.parse(SOURCE.read_text())
    warnings = [node for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "warning"
                and node.args and isinstance(node.args[0], ast.Constant)
                and str(node.args[0].value).startswith("context_assembler_retrieve_failed")]
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.args[0].value == "context_assembler_retrieve_failed error_type=%s"
    assert len(warning.args) == 2
    assert isinstance(warning.args[1], ast.Attribute)
    assert warning.args[1].attr == "__name__"
