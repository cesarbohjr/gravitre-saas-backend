"""Contract checks for provenance-gated ECO-003 log aggregation and privacy."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "eco003_context_stage_latency_report", ROOT / "scripts/eco003_context_stage_latency_report.py"
)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


def test_real_stage_records_support_p50_p95_with_explicit_sample_counts():
    lines = [
        "eco003_context_stage stage=org_context outcome=ok duration_ms=10.000",
        "eco003_context_stage stage=org_context outcome=ok duration_ms=20.000",
        "eco003_context_stage stage=org_context outcome=error duration_ms=5.000",
        "eco003_context_stage stage=external_research outcome=ok duration_ms=50.000",
    ]
    result = module.summarize(lines, provenance="verified_nonproduction", min_samples=1)
    context = result["stage_summaries"]["org_context"]
    assert context == {"samples": 2, "errors": 1, "p50_ms": 15, "p95_ms": 19.5}
    assert result["stage_summaries"]["external_research"]["p95_ms"] == 50


@pytest.mark.parametrize("lines,provenance,count", [
    ([], "fixture", 1),
    ([], "verified_nonproduction", 1),
    (["eco003_context_stage stage=org_context outcome=ok duration_ms=1.000"], "verified_nonproduction", 30),
    (["eco003_context_stage stage=org_context outcome=ok duration_ms=nan"], "verified_nonproduction", 1),
    (["eco003_context_stage stage=other_org outcome=ok duration_ms=1.000"], "verified_nonproduction", 1),
])
def test_rejects_unverified_empty_under_sampled_or_unknown_inputs(lines, provenance, count):
    with pytest.raises(ValueError):
        module.summarize(lines, provenance=provenance, min_samples=count)


def test_retrieval_failure_logging_exposes_only_error_class():
    source = (ROOT / "app/services/context_assembler.py").read_text()
    tree = ast.parse(source)
    warnings = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "warning"
        and node.args and isinstance(node.args[0], ast.Constant)
        and str(node.args[0].value).startswith("context_assembler_retrieve_failed")
    ]
    assert len(warnings) == 1
    message = warnings[0].args[0].value
    assert message == "context_assembler_retrieve_failed error_type=%s"
    assert len(warnings[0].args) == 2
    error_arg = warnings[0].args[1]
    assert isinstance(error_arg, ast.Attribute)
    assert error_arg.attr == "__name__"


def test_scoped_reads_still_pass_org_user_environment_and_actor():
    source = (ROOT / "app/services/context_assembler.py").read_text()
    assert "org_id=org_id" in source
    assert "user_id=user_id" in source
    assert "environment_name=environment_name" in source
    assert "agent=agent_payload" in source
    assert "assignments or []" in source
    assert "asyncio.gather" not in source
