from app.plays.outcomes import AttributionType
from app.plays.verification import (
    SourceVerificationEvidence,
    record_source_verified_play_result,
)


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, name, rows, inserts):
        self.name = name
        self.rows = list(rows)
        self.inserts = inserts
        self.pending = None

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if str(row.get(key)) == str(value)]
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    def insert(self, row):
        self.pending = dict(row)
        return self

    def execute(self):
        if self.pending is not None:
            self.inserts.append(self.pending)
            return _Response([self.pending])
        return _Response(self.rows)


class _Client:
    def __init__(self, rows):
        self.rows = rows
        self.inserts = []

    def table(self, name):
        assert name == "intelligence_outcome_events"
        return _Query(name, self.rows, self.inserts)


def _actioned():
    return {
        "id": "out-actioned",
        "org_id": "org-1",
        "outcome_event": "play_business_result",
        "entity_type": "invoice",
        "entity_id": "inv-42",
        "workflow_id": "wf-1",
        "workflow_run_id": "run-1",
        "agent_id": "agent-1",
        "connector_id": "conn-1",
        "metadata": {
            "play_key": "revenue-recovery",
            "play_version": "1",
            "play_instance_id": "play-1",
            "verification_state": "ACTIONED",
            "action_tools": ["quickbooks.invoices.create"],
            "evidence_ids": ["obs-action"],
        },
    }


def test_source_verified_result_appends_new_event_and_preserves_actioned_lineage():
    client = _Client([_actioned()])
    result = record_source_verified_play_result(
        client,
        org_id="org-1",
        actioned_outcome_id="out-actioned",
        evidence=SourceVerificationEvidence(
            system="quickbooks",
            record_type="invoice",
            record_id="inv-42",
            method="source_of_record_re_read",
            observed_at="2026-09-29T13:00:00+00:00",
            baseline_value=2500.0,
            result_value=0.0,
            outcome_type="recovered_revenue",
            metric_key="open_invoice_balance",
            unit="revenue",
            currency="USD",
            evidence_ids=("obs-reread",),
        ),
        success=True,
        attribution_type=AttributionType.DIRECT,
    )
    assert len(client.inserts) == 1
    assert result["metadata"]["verification_state"] == "VERIFIED SUCCESS"
    assert result["metadata"]["verified_from_actioned_outcome_id"] == "out-actioned"
    assert result["metadata"]["source_of_record_verified"] is True
    assert result["metadata"]["provider_acceptance_is_business_verification"] is False
    assert result["metadata"]["source_records"][0] == {
        "system": "quickbooks",
        "record_type": "invoice",
        "record_id": "inv-42",
    }
    assert result["metadata"]["evidence_ids"] == ["obs-action", "obs-reread"]
    assert result["before_value"] == 2500.0
    assert result["after_value"] == 0.0
    assert result["measured_at"] == "2026-09-29T13:00:00+00:00"


def test_source_verification_rejects_non_actioned_or_cross_tenant_event():
    client = _Client([{**_actioned(), "org_id": "org-other"}])
    try:
        record_source_verified_play_result(
            client,
            org_id="org-1",
            actioned_outcome_id="out-actioned",
            evidence=SourceVerificationEvidence(
                system="quickbooks",
                record_type="invoice",
                record_id="inv-42",
                method="source_of_record_re_read",
                observed_at="2026-09-29T13:00:00+00:00",
                baseline_value=2500.0,
                result_value=0.0,
                outcome_type="recovered_revenue",
            ),
            success=True,
        )
    except ValueError as exc:
        assert "ACTIONED" in str(exc)
    else:
        raise AssertionError("expected cross-tenant/non-actioned verification refusal")


def test_source_verification_requires_measured_result():
    evidence = SourceVerificationEvidence(
        system="quickbooks",
        record_type="invoice",
        record_id="inv-42",
        method="source_of_record_re_read",
        observed_at="2026-09-29T13:00:00+00:00",
        baseline_value=2500.0,
        result_value=None,
        outcome_type="recovered_revenue",
    )
    try:
        evidence.validate()
    except ValueError as exc:
        assert "measured result" in str(exc)
    else:
        raise AssertionError("expected missing measurement refusal")


def test_source_success_requires_business_metric_and_baseline():
    client = _Client([_actioned()])
    evidence = SourceVerificationEvidence(
        system="quickbooks",
        record_type="invoice",
        record_id="inv-42",
        method="source_of_record_re_read",
        observed_at="2026-09-29T13:00:00+00:00",
        baseline_value=None,
        result_value=0.0,
        outcome_type="recovered_revenue",
        metric_key="open_invoice_balance",
    )
    try:
        record_source_verified_play_result(
            client,
            org_id="org-1",
            actioned_outcome_id="out-actioned",
            evidence=evidence,
            success=True,
        )
    except ValueError as exc:
        assert "baseline" in str(exc)
    else:
        raise AssertionError("expected missing baseline refusal")


def test_action_execution_source_read_cannot_be_business_verified_success():
    client = _Client([_actioned()])
    evidence = SourceVerificationEvidence(
        system="quickbooks",
        record_type="invoice",
        record_id="inv-42",
        method="source_of_record_re_read",
        observed_at="2026-09-29T13:00:00+00:00",
        baseline_value=2500.0,
        result_value=0.0,
        outcome_type="action_execution",
        metric_key="open_invoice_balance",
    )
    try:
        record_source_verified_play_result(
            client,
            org_id="org-1",
            actioned_outcome_id="out-actioned",
            evidence=evidence,
            success=True,
        )
    except ValueError as exc:
        assert "business-result" in str(exc)
    else:
        raise AssertionError("expected action-only verification refusal")
