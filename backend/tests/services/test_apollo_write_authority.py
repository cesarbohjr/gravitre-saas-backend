"""Dedicated catalog_write_authority checks for Apollo destructive actions (Batch 1)."""
from __future__ import annotations

from app.connectors.action_catalog.registry import get_action_spec
from app.services.catalog_write_authority import (
    invoke_action_requires_write_approval,
    matrix_entry_requires_write_approval,
)


def test_apollo_contacts_delete_requires_approval() -> None:
    spec = get_action_spec("apollo.contacts.delete")
    assert spec is not None
    assert spec.destructive is True
    assert spec.requires_approval is True
    assert matrix_entry_requires_write_approval(spec) is True
    assert invoke_action_requires_write_approval("apollo.contacts.delete") is True


def test_apollo_sequences_remove_requires_approval() -> None:
    spec = get_action_spec("apollo.sequences.remove")
    assert spec is not None
    assert spec.destructive is True
    assert invoke_action_requires_write_approval("apollo.sequences.remove") is True


def test_apollo_people_match_is_read_no_approval() -> None:
    spec = get_action_spec("apollo.people.match")
    assert spec is not None
    assert spec.kind == "read"
    assert invoke_action_requires_write_approval("apollo.people.match") is False


def test_apollo_organizations_enrich_is_read_no_approval() -> None:
    spec = get_action_spec("apollo.organizations.enrich")
    assert spec is not None
    assert spec.kind == "read"
    assert invoke_action_requires_write_approval("apollo.organizations.enrich") is False
