"""PR605 method-call and registry evidence boundaries."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pr605_execution_owner_edges.py"
spec = importlib.util.spec_from_file_location("pr605_execution_owner_edges", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_import_alias_and_call_line_resolution():
    src = ("from app.services.domain_events import DomainEventRelay as Relay\n"
           "from app.services import execution_outcome as outcomes\n"
           "def work():\n"
           "    Relay(None)\n"
           "    outcomes.emit_outcome()\n")
    row = module.inspect_python(src, "test.py")
    targets = {c["target"] for c in row["direct_call_edges"]}
    assert "app.services.domain_events.DomainEventRelay" in targets
    assert "app.services.execution_outcome.emit_outcome" in targets
    assert all(isinstance(c["line"], int) for c in row["direct_call_edges"])


def test_dynamic_registration_not_counted_as_executed():
    row = module.inspect_python(
        "from app.services.domain_events import register_handler\n"
        "register_handler('source.disconnected', handler)\n"
        "getattr(obj, name)()\n",
        "test.py",
    )
    assert any("register_handler" in c["target"] for c in row["registry_call_candidates"])
    assert row["direct_call_edges"]
    assert not any("getattr" in c["target"] for c in row["direct_call_edges"])


def test_real_source_inventory_remains_non_authoritative_for_retirement():
    data = module.collect()
    assert not data["missing_sources"]
    assert len(data["critical_owners_present"]) == len(module.CRITICAL)
    assert len(data["sources"]) == len(module.SOURCES)
    assert data["runtime_executions_observed"] == 0
    assert data["retirement_certified"] is False
