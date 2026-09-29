from app.plays.evidence import build_play_evidence_chain


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def execute(self):
        return _Response(self.rows)


class _Client:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _Query([dict(row) for row in self.tables.get(name, [])])


def test_evidence_chain_joins_metric_play_run_approval_source_and_verification():
    client = _Client(
        {
            "intelligence_outcome_events": [
                {
                    "id": "out-1",
                    "org_id": "org-1",
                    "outcome_event": "play_business_result",
                    "entity_type": "invoice",
                    "entity_id": "inv-42",
                    "workflow_id": "wf-1",
                    "workflow_run_id": "run-1",
                    "agent_id": "agent-1",
                    "connector_id": "conn-1",
                    "confidence_score": 1.0,
                    "before_value": 0.0,
                    "after_value": 2500.0,
                    "measured_at": "2026-09-29T10:00:00+00:00",
                    "measurement_status": "recorded",
                    "metadata": {
                        "play_key": "revenue-recovery",
                        "play_version": "1",
                        "play_instance_id": "play-run-1",
                        "outcome_type": "recovered_revenue",
                        "metric_key": "recovered_revenue",
                        "delta_value": 2500.0,
                        "unit": "revenue",
                        "currency": "USD",
                        "action_tools": ["quickbooks.invoices.create"],
                        "evidence_ids": ["obs-1"],
                        "source_records": [
                            {
                                "system": "quickbooks",
                                "record_type": "invoice",
                                "record_id": "inv-42",
                            }
                        ],
                        "verification_state": "VERIFIED SUCCESS",
                        "verification_method": "source_of_record_re_read",
                        "verified": True,
                        "attribution_type": "direct",
                        "attribution_weight": 1.0,
                    },
                    "created_at": "2026-09-29T10:00:00+00:00",
                }
            ],
            "workflow_runs": [
                {
                    "id": "run-1",
                    "org_id": "org-1",
                    "workflow_id": "wf-1",
                    "status": "completed",
                    "approval_status": "approved",
                    "required_approvals": 1,
                }
            ],
            "approvals": [
                {
                    "id": "approval-1",
                    "org_id": "org-1",
                    "run_id": "run-1",
                    "status": "approved",
                    "title": "Approve workflow",
                }
            ],
        }
    )

    chain = build_play_evidence_chain(
        client,
        "org-1",
        "out-1",
        play_key="revenue-recovery",
    )

    assert chain is not None
    assert chain["metric"]["delta"] == 2500.0
    assert chain["entity"] == {"type": "invoice", "id": "inv-42"}
    assert chain["play"]["key"] == "revenue-recovery"
    assert chain["workflow"]["run"]["status"] == "completed"
    assert chain["execution"]["actions"] == ["quickbooks.invoices.create"]
    assert chain["governance"]["approvals"][0]["status"] == "approved"
    assert chain["sourceRecords"][0]["record_id"] == "inv-42"
    assert chain["verification"]["state"] == "VERIFIED SUCCESS"
    assert chain["truth"]["executionSuccessIsBusinessSuccess"] is False


def test_evidence_chain_is_tenant_and_play_scoped():
    client = _Client(
        {
            "intelligence_outcome_events": [
                {
                    "id": "out-1",
                    "org_id": "org-2",
                    "outcome_event": "play_business_result",
                    "metadata": {"play_key": "revenue-recovery"},
                }
            ]
        }
    )
    assert build_play_evidence_chain(client, "org-1", "out-1") is None


def test_play_mismatch_does_not_leak_outcome():
    client = _Client(
        {
            "intelligence_outcome_events": [
                {
                    "id": "out-1",
                    "org_id": "org-1",
                    "outcome_event": "play_business_result",
                    "metadata": {"play_key": "customer-rescue"},
                }
            ]
        }
    )
    assert (
        build_play_evidence_chain(
            client,
            "org-1",
            "out-1",
            play_key="revenue-recovery",
        )
        is None
    )
