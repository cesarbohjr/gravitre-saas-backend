from types import SimpleNamespace

import pytest

from app.capabilities.native_bindings import bind_component


class _Query:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.upserted = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        if self.rows and key in self.rows[0]:
            self.rows = [row for row in self.rows if row.get(key) == value]
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def upsert(self, payload, **_kwargs):
        self.upserted = payload
        self.rows = [payload]
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class _Client:
    def __init__(self, tables):
        self.tables = tables
        self.last = {}

    def table(self, name):
        rows = self.tables.get(name, [])
        query = _Query(rows)
        self.last[name] = query
        return query


def _package(kind: str, name: str, *, status: str = "installed"):
    return {
        "id": "pkg-1",
        "status": status,
        "inspection": {"components": [{"kind": kind, "name": name}]},
    }


def test_agent_declaration_binds_only_to_existing_org_agent() -> None:
    client = _Client({"agents": [{"id": "agent-1", "org_id": "org-1"}]})
    row = bind_component(
        client,
        org_id="org-1",
        package=_package("agent", "researcher"),
        component_kind="agent",
        component_name="researcher",
        target_type="agent",
        target_id="agent-1",
        user_id="user-1",
    )
    assert row["target_id"] == "agent-1"
    assert row["enabled"] is True


def test_binding_rejects_undeclared_component() -> None:
    client = _Client({"agents": [{"id": "agent-1", "org_id": "org-1"}]})
    with pytest.raises(ValueError, match="not declared"):
        bind_component(
            client,
            org_id="org-1",
            package=_package("agent", "researcher"),
            component_kind="agent",
            component_name="other",
            target_type="agent",
            target_id="agent-1",
            user_id="user-1",
        )


def test_binding_rejects_uninstalled_package() -> None:
    client = _Client({})
    with pytest.raises(ValueError, match="must be installed"):
        bind_component(
            client,
            org_id="org-1",
            package=_package("trigger", "nightly", status="quarantined"),
            component_kind="trigger",
            component_name="nightly",
            target_type="workflow_schedule",
            target_id="schedule-1",
            user_id="user-1",
        )


def test_trigger_cannot_bind_to_agent() -> None:
    client = _Client({})
    with pytest.raises(ValueError, match="Unsupported native binding"):
        bind_component(
            client,
            org_id="org-1",
            package=_package("trigger", "nightly"),
            component_kind="trigger",
            component_name="nightly",
            target_type="agent",
            target_id="agent-1",
            user_id="user-1",
        )


def test_private_other_org_marketplace_asset_is_not_valid_template_target() -> None:
    client = _Client(
        {
            "marketplace_assets": [
                {
                    "id": "asset-1",
                    "org_id": "org-2",
                    "visibility": "private",
                    "status": "draft",
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="target was not found"):
        bind_component(
            client,
            org_id="org-1",
            package=_package("template", "proposal"),
            component_kind="template",
            component_name="proposal",
            target_type="marketplace_asset",
            target_id="asset-1",
            user_id="user-1",
        )


def test_published_public_marketplace_asset_is_valid_template_target() -> None:
    client = _Client(
        {
            "marketplace_assets": [
                {
                    "id": "asset-1",
                    "org_id": "org-2",
                    "visibility": "public",
                    "status": "published",
                }
            ]
        }
    )
    row = bind_component(
        client,
        org_id="org-1",
        package=_package("template", "proposal"),
        component_kind="template",
        component_name="proposal",
        target_type="marketplace_asset",
        target_id="asset-1",
        user_id="user-1",
    )
    assert row["target_type"] == "marketplace_asset"
