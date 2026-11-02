"""Current implementation is exercised; candidate SDK results are never faked."""
import importlib.util
import json
from pathlib import Path
from dataclasses import replace
import sys

import pytest

from tests.support.governed_memory_benchmark import execute_case

ROOT = Path(__file__).resolve().parents[3]
CASES = json.loads((ROOT / "scripts/memory_benchmark/cases.json").read_text())
spec = importlib.util.spec_from_file_location("memory_candidate_contracts", ROOT / "scripts/memory_benchmark/contracts.py")
contracts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contracts
spec.loader.exec_module(contracts)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
async def test_current_canonical_kernel_against_governed_memory_cases(case):
    result = await execute_case(case)
    assert result["passed"], result


def test_mem0_request_matches_pinned_shape_and_uses_tenant_bound_namespace():
    scope = contracts.Scope("org-a", "user-a", "agent-a")
    request = contracts.mem0_search_contract(scope, "synthetic preference", namespace_key=b"x" * 32)
    assert set(request) == {"query", "top_k", "filters"}
    assert set(request["filters"]) == {"user_id", "agent_id"}
    assert all(len(v) == 64 for v in request["filters"].values())
    assert all(v not in json.dumps(request) for v in (scope.org_id, scope.user_id, scope.agent_id))
    other = contracts.mem0_search_contract(replace(scope, org_id="org-b"), "synthetic preference", namespace_key=b"x" * 32)
    assert request["filters"]["user_id"] != other["filters"]["user_id"]
    assert request["filters"]["agent_id"] != other["filters"]["agent_id"]
    # Ambiguous delimiter concatenation must not collide across identities.
    assert contracts.mem0_search_contract(contracts.Scope("a:b", "c", "d"), "fixture", namespace_key=b"x" * 32) != contracts.mem0_search_contract(contracts.Scope("a", "b:c", "d"), "fixture", namespace_key=b"x" * 32)


def test_provider_text_metadata_and_unknown_ids_cannot_replace_authoritative_rows():
    response = {"results": [{"id": "vendor-id", "memory": "UNTRUSTED PRIVATE TEXT", "metadata": {"org_id": "foreign"}},
                            {"id": "unknown"}, {"id": "vendor-id"}]}
    assert contracts.canonical_mem0_hit_ids(response, trusted_bindings={"vendor-id": "canonical-id"}) == ["canonical-id"]
    with pytest.raises(ValueError):
        contracts.canonical_mem0_hit_ids(response, trusted_bindings={"vendor-id": True})


@pytest.mark.parametrize("response", [None, {"results": "bad"}, {"results": [None]}, {"results": [{"id": 1}]}, {"results": [{}] * 51}])
def test_malformed_vendor_results_fail_closed(response):
    with pytest.raises(ValueError):
        contracts.canonical_mem0_hit_ids(response, trusted_bindings={})


def test_letta_is_explicitly_a_read_only_reference_contract_with_no_implemented_transport():
    contract = contracts.letta_snapshot_requirements()
    assert contract["runtime_status"] == "NOT_RUN" and contract["transport"] is None
    assert not contract["allow_self_edit"] and not contract["allow_skill_or_prompt_mutation"]
    assert not contract["allow_cross_agent_search"] and contract["require_authoritative_rehydration"]


def test_upstream_audit_contains_immutable_pins_and_no_claimed_vendor_runs():
    import re
    audit = json.loads((ROOT / "scripts/memory_benchmark/upstream_audit.json").read_text())
    assert audit["sdk_imported"] is False and audit["live_requests"] == 0
    assert {r["id"] for r in audit["candidates"]} == {"mem0", "letta", "letta-code"}
    for row in audit["candidates"]:
        assert re.fullmatch(r"[0-9a-f]{40}", row["revision"])
        assert row["runtime_status"] == "NOT_RUN"
        assert row["license"] == "Apache-2.0"
        assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in row["files"].values())


RECALL_CASES = [case for case in CASES if case.get("operation") != "learn"]
REPLAY_CASES = json.loads((ROOT / "scripts/memory_benchmark/replay_cases.json").read_text())


@pytest.mark.asyncio
@pytest.mark.parametrize("case", RECALL_CASES + REPLAY_CASES, ids=lambda case: case["id"])
async def test_mem0_shaped_fixture_results_cross_real_canonical_gates(case):
    result = await execute_case(case, retrieval="mem0_contract_replay")
    assert result["passed"], result


@pytest.mark.asyncio
async def test_candidate_search_replay_cannot_be_mislabeled_as_learning():
    with pytest.raises(ValueError, match="cannot certify candidate learning"):
        await execute_case({"operation": "learn"}, retrieval="mem0_contract_replay")


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_mode", ["canonical_fixture", "mem0_contract_replay"])
async def test_report_fails_if_either_arm_fails_and_keeps_vendor_status_honest(failed_mode):
    from unittest.mock import patch

    spec = importlib.util.spec_from_file_location("memory_replay_runner", ROOT / "scripts/memory_benchmark/run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    async def result(case, *, retrieval="canonical_fixture"):
        if retrieval == failed_mode and case["id"] == "authorized_fact":
            # Exception bodies must never leak into evidence reports.
            raise RuntimeError("PRIVATE_VENDOR_PAYLOAD")
        return {"id": case["id"], "passed": True}

    with patch("tests.support.governed_memory_benchmark.execute_case", side_effect=result):
        report = await runner.run_reference()
    assert report["status"] == "FAIL"
    assert (report["reference_status"] == "FAIL") == (failed_mode == "canonical_fixture")
    assert (report["contract_replay"]["status"] == "FAIL") == (failed_mode == "mem0_contract_replay")
    assert report["contract_replay"]["case_count"] == 31
    assert report["contract_replay"]["candidate_engine_status"] == "NOT_RUN"
    assert not report["contract_replay"]["sdk_imported"]
    assert all(row["status"] == "NOT_RUN" for row in report["candidate_results"])
    assert not report["production_certified"] and report["adoption_decision"] == "none"
    assert "PRIVATE_VENDOR_PAYLOAD" not in json.dumps(report)
