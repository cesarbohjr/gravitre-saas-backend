from app.services import dataset_target_validation as mod


class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self.rows = list(rows)

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if str(row.get(key)) == str(value)]
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    def execute(self):
        return _Response(self.rows)


class _Client:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        return _Query(self.tables.get(name, []))


def test_play_workflow_and_agent_use_existing_canonical_sources(monkeypatch):
    client = _Client()
    monkeypatch.setattr(mod, "get_platform_play", lambda key: object() if key == "revenue-recovery" else None)
    monkeypatch.setattr(mod, "get_workflow_def", lambda _c, _o, wid: {"id": wid} if wid == "wf-1" else None)
    monkeypatch.setattr(mod, "get_operator", lambda _c, _o, aid: {"id": aid} if aid == "agent-1" else None)

    assert mod.dataset_target_exists(client, "org-1", target_type="play", target_id="revenue-recovery")
    assert mod.dataset_target_exists(client, "org-1", target_type="workflow", target_id="wf-1")
    assert mod.dataset_target_exists(client, "org-1", target_type="agent", target_id="agent-1")
    assert not mod.dataset_target_exists(client, "org-1", target_type="workflow", target_id="wf-missing")


def test_model_department_and_evaluation_are_tenant_scoped():
    client = _Client(
        {
            "ml_models": [
                {"id": "model-1", "org_id": "org-1"},
                {"id": "model-2", "org_id": "org-2"},
            ],
            "agents": [{"id": "agent-1", "org_id": "org-1", "department": "finance"}],
            "response_evaluations": [
                {"id": "eval-1", "org_id": "org-1"},
                {"id": "eval-2", "org_id": "org-2"},
            ],
        }
    )

    assert mod.dataset_target_exists(client, "org-1", target_type="model", target_id="model-1")
    assert not mod.dataset_target_exists(client, "org-1", target_type="model", target_id="model-2")
    assert mod.dataset_target_exists(client, "org-1", target_type="department", target_id="finance")
    assert mod.dataset_target_exists(client, "org-1", target_type="evaluation", target_id="eval-1")
    assert not mod.dataset_target_exists(client, "org-1", target_type="evaluation", target_id="eval-2")


def test_require_target_fails_closed_for_missing_or_lookup_failure(monkeypatch):
    client = _Client()
    try:
        mod.require_dataset_target(client, "org-1", target_type="model", target_id="missing")
    except LookupError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("missing target must be refused")

    monkeypatch.setattr(mod, "dataset_target_exists", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("db down")))
    try:
        mod.require_dataset_target(client, "org-1", target_type="model", target_id="model-1")
    except RuntimeError as exc:
        assert "Could not verify canonical" in str(exc)
    else:
        raise AssertionError("unverifiable target must fail closed")
