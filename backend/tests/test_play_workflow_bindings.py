from app.plays.workflow_bindings import (
    bind_play_to_workflow,
    list_play_workflow_bindings,
    unbind_play_from_workflow,
)


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.update_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if str(row.get(key)) == str(value)]
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def update(self, payload):
        self.update_payload = payload
        for row in self.rows:
            row.update(payload)
        return self

    def execute(self):
        return _Response(self.rows)


class _Client:
    def __init__(self, workflows):
        self.workflows = workflows

    def table(self, name):
        if name == "workflow_defs":
            return _Query(self.workflows)
        if name == "workflows":
            return _Query([])
        raise AssertionError(name)


def test_binding_adds_play_metadata_without_owning_execution(monkeypatch):
    rows = [
        {
            "id": "wf-1",
            "org_id": "org-1",
            "name": "Collections",
            "config": {"existing": True},
        }
    ]
    client = _Client(rows)
    monkeypatch.setattr(
        "app.plays.workflow_bindings.mirror_legacy_workflow_row_to_contract",
        lambda *_args, **_kwargs: None,
    )

    result = bind_play_to_workflow(
        client,
        "org-1",
        play_key="revenue-recovery",
        workflow_id="wf-1",
        actor_id="user-1",
        environment_name="default",
    )

    assert result["executionAuthority"] == "canonical_workflow_runtime"
    assert rows[0]["config"]["existing"] is True
    assert rows[0]["config"]["play"]["key"] == "revenue-recovery"
    assert "steps" not in rows[0]["config"]["play"]


def test_bindings_are_org_and_play_scoped():
    client = _Client(
        [
            {
                "id": "wf-1",
                "org_id": "org-1",
                "name": "Collections",
                "config": {"play": {"key": "revenue-recovery"}},
            },
            {
                "id": "wf-2",
                "org_id": "org-1",
                "name": "Support",
                "config": {"play": {"key": "customer-rescue"}},
            },
            {
                "id": "wf-3",
                "org_id": "org-2",
                "name": "Other tenant",
                "config": {"play": {"key": "revenue-recovery"}},
            },
        ]
    )
    rows = list_play_workflow_bindings(client, "org-1", "revenue-recovery")
    assert [row["workflowId"] for row in rows] == ["wf-1"]


def test_unbind_preserves_unrelated_workflow_config(monkeypatch):
    rows = [
        {
            "id": "wf-1",
            "org_id": "org-1",
            "name": "Collections",
            "config": {
                "existing": {"keep": True},
                "play": {"key": "revenue-recovery"},
            },
        }
    ]
    client = _Client(rows)
    monkeypatch.setattr(
        "app.plays.workflow_bindings.mirror_legacy_workflow_row_to_contract",
        lambda *_args, **_kwargs: None,
    )
    result = unbind_play_from_workflow(
        client,
        "org-1",
        play_key="revenue-recovery",
        workflow_id="wf-1",
        environment_name="default",
    )
    assert result["bound"] is False
    assert rows[0]["config"] == {"existing": {"keep": True}}
