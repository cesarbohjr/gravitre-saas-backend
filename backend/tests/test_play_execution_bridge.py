from app.services.execution_outcome import (
    ExecutionOutcomeEvent,
    VerifiedOutputRef,
    _record_play_actioned_result,
)


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table, rows, inserted):
        self.table_name = table
        self.rows = rows
        self.inserted = inserted
        self.pending_insert = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if str(row.get(key)) == str(value)]
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def insert(self, row):
        self.pending_insert = dict(row)
        return self

    def execute(self):
        if self.pending_insert is not None:
            self.inserted.append((self.table_name, self.pending_insert))
            return _Response([self.pending_insert])
        return _Response(self.rows)


class _Client:
    def __init__(self, run_parameters):
        self.run_parameters = run_parameters
        self.inserted = []

    def table(self, name):
        if name == "workflow_runs":
            return _Query(
                name,
                [{"id": "run-1", "org_id": "org-1", "parameters": self.run_parameters}],
                self.inserted,
            )
        if name == "intelligence_outcome_events":
            return _Query(name, [], self.inserted)
        raise AssertionError(name)


def test_play_bound_write_records_actioned_not_verified_success():
    client = _Client(
        {
            "play": {
                "key": "revenue-recovery",
                "version": "1",
                "execution_authority": "canonical_workflow_runtime",
            }
        }
    )
    event = ExecutionOutcomeEvent(
        org_id="org-1",
        status="completed",
        source="api",
        run_id="run-1",
        workflow_id="wf-1",
        verified_output=VerifiedOutputRef(
            entity_type="invoice",
            entity_id="inv-42",
            integration="quickbooks",
        ),
        metadata={
            "invoke_action": "quickbooks.invoices.create",
            "work_object_id": "work-1",
        },
    )
    assert _record_play_actioned_result(
        client,
        event,
        "completed",
        "2026-09-29T12:00:00+00:00",
    ) is True

    inserted = [row for table, row in client.inserted if table == "intelligence_outcome_events"]
    assert len(inserted) == 1
    row = inserted[0]
    assert row["outcome_event"] == "play_business_result"
    assert row["metadata"]["verification_state"] == "ACTIONED"
    assert row["metadata"]["verified"] is False
    assert row["metadata"]["provider_acceptance_is_business_verification"] is False
    assert row["measured_at"] is None


def test_play_bound_read_only_completion_does_not_record_actioned():
    client = _Client({"play": {"key": "revenue-recovery", "version": "1"}})
    event = ExecutionOutcomeEvent(
        org_id="org-1",
        status="completed",
        source="api",
        run_id="run-1",
        workflow_id="wf-1",
        metadata={},
    )
    assert _record_play_actioned_result(
        client,
        event,
        "completed",
        "2026-09-29T12:00:00+00:00",
    ) is False
    assert client.inserted == []


def test_unbound_workflow_never_creates_play_result():
    client = _Client({})
    event = ExecutionOutcomeEvent(
        org_id="org-1",
        status="completed",
        source="api",
        run_id="run-1",
        workflow_id="wf-1",
        metadata={"invoke_action": "quickbooks.invoices.create"},
    )
    assert _record_play_actioned_result(
        client,
        event,
        "completed",
        "2026-09-29T12:00:00+00:00",
    ) is False
    assert client.inserted == []
