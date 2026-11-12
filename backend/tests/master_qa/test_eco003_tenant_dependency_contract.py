"""ECO-003: authorization-scoped dependencies and safe concurrency inventory.

These static checks do not substitute for independently observed two-tenant
nonproduction acceptance; they prevent silent loss of tenant parameters.
"""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "app/services/context_assembler.py"


def _calls():
    tree = ast.parse(SOURCE.read_text())
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)]


def _method_call(name):
    matches = [n for n in _calls()
               if isinstance(n.func, ast.Attribute) and n.func.attr == name]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def test_retrieval_has_explicit_tenant_user_and_environment_scope():
    call = _method_call("retrieve")
    kwargs = {kw.arg: kw.value for kw in call.keywords}
    for field, variable in (("org_id", "org_id"),
                            ("user_id", "user_id"),
                            ("environment_name", "environment_name")):
        assert isinstance(kwargs[field], ast.Name)
        assert kwargs[field].id == variable
    assert isinstance(kwargs["client"], ast.Name)
    assert kwargs["client"].id == "db_client"


def test_company_and_research_are_tenant_scoped():
    company = _method_call("get_context_for_prompt")
    research = _method_call("research")
    for call in (company, research):
        assert call.args and isinstance(call.args[0], ast.Name)
        assert call.args[0].id == "org_id"
    assert isinstance(research.args[1], ast.Name)
    assert research.args[1].id == "request"


def test_sequential_dependency_order_preserved_until_real_profiling():
    tree = ast.parse(SOURCE.read_text())
    method_lines = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute):
                method_lines[func.attr] = node.lineno
    assert method_lines["retrieve"] < method_lines["get_context_for_prompt"] < method_lines["research"]
