"""Every Outcome Pack passes the generic contract certification through production machinery."""
from __future__ import annotations

import pytest

from app.marketplace.marketplace3.certification import (
    CONTRACT_CHECKS,
    certify_all_outcome_packs,
    certify_outcome_contract,
)
from app.outcome_packs.registry import get_pack, list_packs

EXPECTED_PACKS = {"growth-pipeline", "marketing-seo", "sales-pipeline", "msp-service-desk", "customer-success"}


def test_registry_carries_every_department_pack():
    assert EXPECTED_PACKS <= {p.pack_id for p in list_packs()}


@pytest.mark.parametrize("pack_id", sorted(EXPECTED_PACKS))
def test_pack_is_certified_complete(pack_id):
    result = certify_outcome_contract(get_pack(pack_id))
    failing = [(c["key"], c["detail"]) for c in result["checks"] if c["status"] == "fail"]
    assert failing == []
    assert result["complete"] is True
    assert {c["key"] for c in result["checks"]} == {k for k, _, _ in CONTRACT_CHECKS}
    assert result["measurement"]["verified"] > 0


def test_missing_fixture_blocks_completion():
    pack = get_pack("growth-pipeline")
    broken_config = pack.config.model_copy(deep=True)
    broken_config.certification.fixtures.pop("crm-deal-progress")
    broken = type(pack)(pack_id=pack.pack_id, department=pack.department, config=broken_config,
                        raw_config=pack.raw_config, marketplace=pack.marketplace)
    result = certify_outcome_contract(broken)
    check = next(c for c in result["checks"] if c["key"] == "verified_results_produced")
    assert check["status"] == "fail" and "crm-deal-progress" in check["detail"]
    assert result["complete"] is False


def test_matrix_columns_cover_every_pack():
    rows = certify_all_outcome_packs()
    for row in rows:
        assert set(row["columns"]) == {"Metrics", "Plays", "Capabilities", "Verification", "Evidence",
                                       "Attribution", "Dashboard", "Learning", "Fallbacks", "Certification"}
