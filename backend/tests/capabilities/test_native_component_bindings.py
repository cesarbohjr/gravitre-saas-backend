import pytest

from app.capabilities.native_bindings import (
    bind_component,
    deactivate_component_bindings,
)


class _Query:
    def __init__(self, client, table_name: str):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.payload = None
        self.rows = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def upsert(self, payload, **_kwargs):
        self.payload = payload
        self.client.upserts.append((self.table_name, payload))
        self.rows = [{**payload, "id": "binding-1"}]
        return self

    def update(self, payload):
        self.payload = payload
        self.client.updates.append((self.table_name, payload, list(self.filters)))
        self.rows = [{"id": "binding-1"}]
        return self

    def delete(self):
        return self

    def execute(self):
        class R:
            data = self.rows
        return R()


class _Client:
    def __init__(self):
        self.upserts = []
        self.updates = []

    def table(self, name: str):
        q = _Query(self, name)
        if name == "agents":
            q.rows = [{"id": "agent-1"}]
        return q


def _package(status: str = "installed"):
    return {
        "id": "pkg-1",
        "status": status,
        "inspection": {
            "components": [
                {"kind": "agent", "name": "sales-agent"},
                {"kind": "template", "name": "proposal-template"},
            ]
        },
    }


def test_binding_requires_installed_package() -> None:
    with pytest.raises(ValueError, match="installed"):
        bind_component(
            _Client(),
            org_id="org-1",
            package=_package("quarantined"),
            component_kind="agent",
            component_name="sales-agent",
            target_type="agent",
            target_id="agent-1",
            user_id="user-1",
        )


def test_binding_requires_declared_component() -> None:
    with pytest.raises(ValueError, match="not declared"):
        bind_component(
            _Client(),
            org_id="org-1",
            package=_package(),
            component_kind="agent",
            component_name="undeclared-agent",
            target_type="agent",
            target_id="agent-1",
            user_id="user-1",
        )


def test_agent_binding_links_existing_native_object_without_creating_it() -> None:
    client = _Client()
    row = bind_component(
        client,
        org_id="org-1",
        package=_package(),
        component_kind="agent",
        component_name="sales-agent",
        target_type="agent",
        target_id="agent-1",
        user_id="user-1",
    )

    assert row["target_id"] == "agent-1"
    assert client.upserts[0][0] == "capability_component_bindings"
    assert all(table != "agents" for table, _payload in client.upserts)


def test_invalid_binding_kind_target_pair_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported native binding"):
        bind_component(
            _Client(),
            org_id="org-1",
            package=_package(),
            component_kind="agent",
            component_name="sales-agent",
            target_type="workflow",
            target_id="workflow-1",
            user_id="user-1",
        )


def test_package_binding_deactivation_disables_existing_bindings() -> None:
    client = _Client()
    count = deactivate_component_bindings(
        client,
        org_id="org-1",
        package_id="pkg-1",
    )

    assert count == 1
    table, payload, filters = client.updates[0]
    assert table == "capability_component_bindings"
    assert payload == {"enabled": False}
    assert ("org_id", "org-1") in filters
    assert ("package_id", "pkg-1") in filters
