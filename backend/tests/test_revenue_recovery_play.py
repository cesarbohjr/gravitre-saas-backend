from app.plays.revenue_recovery import (
    list_revenue_recovery_signals,
    project_revenue_recovery_signal,
)


def test_projection_never_calls_detected_balance_recovered_revenue():
    row = {
        "id": "sig-1",
        "suggestion_type": "overdue_invoice",
        "target_entity_type": "invoice",
        "target_entity_id": "42",
        "evidence": {
            "source": "quickbooks.invoices.list",
            "overdue_count": 3,
            "sample_invoices": [
                {"id": "42", "balance": 100.0},
                {"id": "43", "balance": 50.0},
            ],
        },
        "suggested_action": "Review collections workflow.",
        "status": "pending_review",
    }
    projected = project_revenue_recovery_signal(row)
    assert projected["status"] == "RECOMMENDED"
    assert projected["sampleFinancials"]["sampleOpenBalance"] == 150.0
    assert projected["sampleFinancials"]["scope"] == "sample_only"
    assert projected["sampleFinancials"]["verifiedRevenueRecovered"] is None
    assert projected["businessResult"]["verified"] is False
    assert projected["businessResult"]["recoveredRevenue"] is None


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return _Response(self.rows)


class _Client:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "optimization_suggestions"
        return _Query(self.rows)


def test_revenue_recovery_filters_to_existing_revenue_signal_types():
    rows = [
        {"id": "1", "suggestion_type": "overdue_invoice", "evidence": {}},
        {"id": "2", "suggestion_type": "stalled_deal", "evidence": {}},
        {"id": "3", "suggestion_type": "slow_step", "evidence": {}},
    ]
    result = list_revenue_recovery_signals(_Client(rows), "org-1")
    assert [row["signalType"] for row in result] == ["overdue_invoice", "stalled_deal"]
