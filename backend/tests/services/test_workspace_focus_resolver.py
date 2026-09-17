from __future__ import annotations

from app.schemas.workspace_focus import WorkspaceFocus
from app.services.workspace_focus_resolver import (
    RESOLUTION_INVALID_TYPE,
    RESOLUTION_NONE,
    RESOLUTION_RESOLVED,
    RESOLUTION_UNRESOLVED,
    format_workspace_focus_compiler_block,
    resolve_workspace_focus,
)


class _Result:
    def __init__(self, data: list) -> None:
        self.data = data


class _Query:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = list(rows)
        self._eq: dict[str, object] = {}

    def select(self, *_args: object, **_kwargs: object) -> _Query:
        return self

    def eq(self, key: str, value: object) -> _Query:
        self._eq[key] = value
        return self

    def is_(self, *_args: object, **_kwargs: object) -> _Query:
        return self

    def limit(self, _n: int) -> _Query:
        return self

    def execute(self) -> _Result:
        rows = self._rows
        for key, value in self._eq.items():
            rows = [row for row in rows if row.get(key) == value]
        return _Result(rows)


class _Client:
    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self._tables = tables

    def table(self, name: str) -> _Query:
        return _Query(self._tables.get(name, []))


def test_missing_focus_is_valid() -> None:
    resolved = resolve_workspace_focus(org_id="org-a", client=_Client({}), focus=None)
    assert resolved["resolution"] == RESOLUTION_NONE


def test_invalid_type_does_not_generic_fetch() -> None:
    focus = WorkspaceFocus.model_validate(
        {
            "route": "/intelligence",
            "selection": {"object_type": "not_a_real_type", "object_id": "x"},
        }
    )
    client = _Client({"org_knowledge_nodes": [{"id": "x", "org_id": "org-a", "name": "Nope"}]})
    resolved = resolve_workspace_focus(org_id="org-a", client=client, focus=focus)
    assert resolved["resolution"] == RESOLUTION_INVALID_TYPE
    assert resolved["canonical"] is None


def test_entity_resolves_in_current_org_only() -> None:
    tables = {
        "org_knowledge_nodes": [
            {"id": "acme", "org_id": "org-a", "name": "Acme", "node_type": "company"},
            {"id": "acme", "org_id": "org-b", "name": "Other tenant Acme", "node_type": "company"},
        ]
    }
    focus = WorkspaceFocus.model_validate(
        {
            "surface": "ai_chat",
            "route": "/intelligence",
            "selection": {"object_type": "entity", "object_id": "acme", "label": "browser label"},
        }
    )
    resolved_a = resolve_workspace_focus(org_id="org-a", client=_Client(tables), focus=focus)
    assert resolved_a["resolution"] == RESOLUTION_RESOLVED
    assert resolved_a["canonical"]["name"] == "Acme"
    assert resolved_a["canonical"]["object_type"] == "company"

    resolved_b_claim = resolve_workspace_focus(org_id="org-b", client=_Client(tables), focus=focus)
    assert resolved_b_claim["canonical"]["name"] == "Other tenant Acme"

    foreign = resolve_workspace_focus(
        org_id="org-c",
        client=_Client(tables),
        focus=focus,
    )
    assert foreign["resolution"] == RESOLUTION_UNRESOLVED
    assert foreign["canonical"] is None
    block = format_workspace_focus_compiler_block(foreign)
    assert "not found in this organization" in block
    assert "browser label" in block
    assert "Other tenant" not in block


def test_wrong_store_does_not_fall_through() -> None:
    tables = {
        "org_knowledge_nodes": [
            {"id": "agt_lead_triage", "org_id": "org-a", "name": "Node", "node_type": "agent"}
        ]
    }
    focus = WorkspaceFocus.model_validate(
        {
            "selection": {"object_type": "agent", "object_id": "agt_lead_triage"},
        }
    )
    resolved = resolve_workspace_focus(org_id="org-a", client=_Client(tables), focus=focus)
    assert resolved["resolution"] == RESOLUTION_UNRESOLVED


def test_workspace_focus_schema_rejects_unknown_keys() -> None:
    try:
        WorkspaceFocus.model_validate({"route": "/ai", "extra": 1})
        raise AssertionError("expected validation error")
    except Exception as exc:
        assert "extra" in str(exc).lower() or "forbidden" in str(exc).lower()


def test_plain_route_without_selection_is_valid() -> None:
    focus = WorkspaceFocus.model_validate({"surface": "ai_chat", "route": "/home"})
    resolved = resolve_workspace_focus(org_id="org-a", client=_Client({}), focus=focus)
    assert resolved["resolution"] == RESOLUTION_NONE
    assert resolved["route"] == "/home"
