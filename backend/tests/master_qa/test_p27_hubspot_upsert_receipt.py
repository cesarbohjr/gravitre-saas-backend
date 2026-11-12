"""ECO-001 HubSpot batch upsert receipt must prove per-record success."""
import importlib
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
mod = importlib.import_module("p27_hubspot_sandbox_readback")


@pytest.mark.parametrize("receipt", [
    None, {}, {"status": "COMPLETE"}, {"status": "COMPLETE", "results": []},
    {"status": "COMPLETE", "results": [{"id": None}]},
    {"status": "COMPLETE", "results": [{"id": "abc"}]},
    {"status": "PENDING", "results": [{"id": "123"}]},
    {"status": "COMPLETE", "results": [{"id": "123"}], "errors": [{"message": "failed"}]},
    {"status": "COMPLETE", "results": [{"id": "123"}, {"id": "456"}]},
])
def test_reject_unverified_write_receipt(receipt):
    with pytest.raises(RuntimeError):
        mod._validated_upsert_receipt(receipt, phase="initial")


def test_accept_candidate_id_but_not_persistence_proof():
    assert mod._validated_upsert_receipt(
        {"status": "COMPLETE", "results": [{"id": "123"}]}, phase="initial"
    ) == "123"
