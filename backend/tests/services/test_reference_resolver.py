"""ReferenceResolver unit tests."""
from __future__ import annotations

from app.services.reference_resolver import resolve_reference, store_active_analysis, store_option_set


def test_confirm_without_pending_is_unmatched() -> None:
    ref = resolve_reference("yes", {})
    assert ref.kind == "confirm"
    assert ref.matched is False


def test_confirm_pending_task() -> None:
    state = {"pending_task": {"status": "awaiting_confirm", "type": "connector_action"}}
    ref = resolve_reference("go ahead", state)
    assert ref.matched is True
    assert ref.pending_target == "pending_task"


def test_store_active_analysis_roundtrip() -> None:
    state = store_active_analysis({}, {"kind": "test", "value": 1})
    ref = resolve_reference("that", state)
    assert ref.matched is True
    assert ref.referent.get("value") == 1


def test_second_one_option() -> None:
    options = [{"id": "a", "label": "First"}, {"id": "b", "label": "Second"}]
    state = store_option_set({}, options)
    ref = resolve_reference("the second one", state)
    assert ref.matched is True
    assert ref.selected_indices == (1,)
