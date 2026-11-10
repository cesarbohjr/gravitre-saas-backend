"""Master board's first sequence: reconcile all 43 without inventing PASS."""
from collections import Counter

from scripts.master_qa_remediation_guard import evaluate


def test_register_reconciliation_exposes_every_original_finding_without_fake_closure():
    report = evaluate()
    rows = report["finding_reconciliation"]
    ids = [row["finding_id"] for row in rows]
    assert len(rows) == report["findings"] == 43
    assert len(set(ids)) == 43
    assert Counter(row["severity"] for row in rows) == {"P0": 30, "P1": 13}
    assert all(row["source_probe_present"] for row in rows)
    assert all(row["still_open"] for row in rows)
    assert all(not row["fix_verified"] for row in rows)
    assert report["release_authorized"] is False
    # An existing test file is only a candidate, not implementation evidence.
    assert all(row["synthetic_status"] != "PASS" for row in rows)


def test_ownership_and_execution_queue_remain_with_existing_prs():
    rows = evaluate()["finding_reconciliation"]
    mapping = {row["finding_id"]: row for row in rows}
    assert mapping["ECO-001"]["implementation_owner"] == "PR611-cross-platform"
    for finding_id in ("ECO-004", "ECO-009", "DEC-010", "DEC-014", "P27-07"):
        assert mapping[finding_id]["implementation_owner"] == "PR610-voice (PR611 integration gate)"
    # ECO-001 is the first P0 routing-authority gap in register order.
    assert next(row["finding_id"] for row in rows if row["severity"] == "P0" and row["still_open"]) == "ECO-001"
