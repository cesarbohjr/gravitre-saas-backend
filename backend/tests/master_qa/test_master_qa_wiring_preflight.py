"""End-to-end SOURCE wiring assertions, not claims of live provider execution."""
from pathlib import Path
from runpy import run_path

ROOT = Path(__file__).resolve().parents[3]
namespace = run_path(str(ROOT / "backend/scripts/master_qa_wiring_preflight.py"),
                     run_name="__wiring_test__")
inspect = namespace["inspect"]

def test_expected_ingress_and_worker_graph_edges_exist():
    evidence = inspect(ROOT)
    assert evidence["source_edges_found"] == evidence["expected_edges"] == 16
    assert not evidence["missing_edges"]
    assert all(edge["proof_level"] == "SOURCE_ONLY_NOT_RUNTIME" for edge in evidence["source_edges"])
    assert evidence["production_certified"] is False

def test_voice_routing_and_connector_auth_remain_explicitly_unverified():
    evidence = inspect(ROOT)
    risks = {r["finding_id"]: r for r in evidence["unresolved_integration_risks"]}
    assert risks["DEC-017"]["live_effect"] == "UNKNOWN"
    assert risks["ECO-005"]["live_effect"] == "UNKNOWN"
    assert risks["P27-08"]["live_effect"] == "NOT_RUN"

def test_missing_live_wiring_cannot_be_misreported_as_connected(tmp_path):
    for finding, path, marker, description in namespace["EDGE_PROBES"]:
        source = tmp_path / path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(marker + "\n")
    initial = inspect(tmp_path)
    assert initial["source_edges_found"] == initial["expected_edges"]
    target = tmp_path / "apps/web/lib/voice-api-proxy.ts"
    target.write_text("/* disconnected */")
    after = inspect(tmp_path)
    assert after["source_edges_found"] < after["expected_edges"]
    assert any(row["finding_id"] == "DEC-017" for row in after["missing_edges"])
    assert not after["production_certified"]
