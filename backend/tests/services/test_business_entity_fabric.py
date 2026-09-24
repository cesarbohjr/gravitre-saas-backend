"""2.0-B BusinessEntity join fabric — no silent merge."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.business_entity_fabric import (
    JOIN_CONFIDENCE_THRESHOLD,
    EntityBinding,
    EntityEvidence,
    join_provider_bindings,
    persist_business_entity,
    website_entity_from_identity,
)
from app.services.entity_resolution_store import _fuzzy_alias_matches


def _company(system: str, rid: str, *, host: str, name: str, confidence: float = 0.9) -> EntityBinding:
    return EntityBinding(
        system=system,
        resource_type="company",
        resource_id=rid,
        confidence=confidence,
        evidence=(
            EntityEvidence(kind="host", value=host, source=system),
            EntityEvidence(kind="legal_name", value=name, source=system),
        ),
    )


def test_website_identity_binds_unique_ga4_and_gsc() -> None:
    entity = website_entity_from_identity(
        org_id="org-1",
        identity={"host": "acme.example", "website": "https://acme.example", "source": "org_settings"},
        ga4_property_id="123456",
        gsc_site_url="https://acme.example",
    )
    assert entity is not None
    systems = {b.system: b.resource_id for b in entity.bindings}
    assert systems["google_analytics"] == "123456"
    assert systems["google_search_console"] == "https://acme.example"


def test_join_hubspot_qbo_on_shared_host() -> None:
    decision = join_provider_bindings(
        org_id="org-1",
        display_name="Acme",
        kind="company",
        left=_company("hubspot", "hs-1", host="acme.example", name="Acme Inc"),
        right=_company("quickbooks", "qbo-1", host="acme.example", name="Acme Inc"),
    )
    assert decision.status == "created"
    assert decision.entity is not None
    assert {b.system for b in decision.entity.bindings} == {"hubspot", "quickbooks"}


def test_no_silent_merge_below_threshold() -> None:
    decision = join_provider_bindings(
        org_id="org-1",
        display_name="Acme",
        kind="company",
        left=_company("hubspot", "hs-1", host="acme.example", name="Acme Inc", confidence=0.5),
        right=_company("quickbooks", "qbo-1", host="acme.example", name="Acme Inc", confidence=0.9),
    )
    assert decision.status == "refused_low_confidence"
    assert decision.entity is None
    assert JOIN_CONFIDENCE_THRESHOLD == 0.85


def test_name_only_company_does_not_silent_merge() -> None:
    left = EntityBinding(
        system="hubspot",
        resource_type="company",
        resource_id="hs-1",
        confidence=0.95,
        evidence=(EntityEvidence(kind="legal_name", value="Acme Inc", source="hubspot"),),
    )
    right = EntityBinding(
        system="zendesk",
        resource_type="organization",
        resource_id="zd-1",
        confidence=0.95,
        evidence=(EntityEvidence(kind="legal_name", value="Acme Inc", source="zendesk"),),
    )
    decision = join_provider_bindings(
        org_id="org-1",
        display_name="Acme Inc",
        kind="company",
        left=left,
        right=right,
    )
    assert decision.status == "refused_ambiguous"


def test_person_join_rejects_fuzzy_first_name() -> None:
    assert _fuzzy_alias_matches(["sarah"], "sarah smith") is True
    left = EntityBinding(
        system="hubspot",
        resource_type="contact",
        resource_id="c1",
        confidence=0.95,
        evidence=(EntityEvidence(kind="name", value="Sarah", source="hubspot"),),
    )
    right = EntityBinding(
        system="zendesk",
        resource_type="user",
        resource_id="z1",
        confidence=0.95,
        evidence=(EntityEvidence(kind="name", value="Sarah Smith", source="zendesk"),),
    )
    decision = join_provider_bindings(
        org_id="org-1",
        display_name="Sarah",
        kind="person",
        left=left,
        right=right,
    )
    assert decision.status == "refused_ambiguous"


def test_person_same_display_name_without_email_does_not_join() -> None:
    left = EntityBinding(
        system="hubspot",
        resource_type="contact",
        resource_id="c1",
        confidence=0.95,
        evidence=(EntityEvidence(kind="name", value="Sarah Smith", source="hubspot"),),
    )
    right = EntityBinding(
        system="zendesk",
        resource_type="user",
        resource_id="z1",
        confidence=0.95,
        evidence=(EntityEvidence(kind="name", value="Sarah Smith", source="zendesk"),),
    )
    decision = join_provider_bindings(
        org_id="org-1",
        display_name="Sarah Smith",
        kind="person",
        left=left,
        right=right,
    )
    assert decision.status == "refused_ambiguous"
    assert decision.entity is None


def test_person_join_on_exact_email() -> None:
    left = EntityBinding(
        system="hubspot",
        resource_type="contact",
        resource_id="c1",
        confidence=0.95,
        evidence=(EntityEvidence(kind="email", value="sarah@acme.example", source="hubspot"),),
    )
    right = EntityBinding(
        system="zendesk",
        resource_type="user",
        resource_id="z1",
        confidence=0.95,
        evidence=(EntityEvidence(kind="email", value="sarah@acme.example", source="zendesk"),),
    )
    decision = join_provider_bindings(
        org_id="org-1",
        display_name="Sarah",
        kind="person",
        left=left,
        right=right,
    )
    assert decision.status == "created"


def test_refuses_existing_distinct_entity_ids() -> None:
    decision = join_provider_bindings(
        org_id="org-1",
        display_name="Acme",
        kind="company",
        left=_company("hubspot", "hs-1", host="acme.example", name="Acme"),
        right=_company("quickbooks", "qbo-1", host="acme.example", name="Acme"),
        existing_left_entity_id="ent-a",
        existing_right_entity_id="ent-b",
    )
    assert decision.status == "refused_ambiguous"


def test_join_store_skipped_for_non_uuid_org() -> None:
    from app.services.business_entity_fabric import persist_join_store

    client = MagicMock()
    entity = website_entity_from_identity(
        org_id="org-1",
        identity={"host": "acme.example"},
        ga4_property_id="123",
    )
    assert entity is not None
    assert persist_join_store(client, entity) == 0
    client.table.assert_not_called()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    entity = website_entity_from_identity(
        org_id="org-1",
        identity={"host": "acme.example"},
        ga4_property_id="123",
    )
    assert entity is not None
    persist_business_entity(client, entity)
    assert client.table.return_value.insert.called
    row = client.table.return_value.insert.call_args[0][0]
    assert row["org_id"] == "org-1"
    assert row["entity_type"] == "business_entity"


def test_fold_hubspot_qbo_zendesk_on_shared_host() -> None:
    from app.services.business_entity_fabric import fold_company_bindings

    decision = fold_company_bindings(
        org_id="org-1",
        display_name="Acme",
        bindings=(
            _company("hubspot", "hs-1", host="acme.example", name="Acme Inc"),
            _company("quickbooks", "qbo-1", host="acme.example", name="Acme Inc"),
            EntityBinding(
                system="zendesk",
                resource_type="organization",
                resource_id="zd-1",
                confidence=0.9,  # confidence-honesty-ok: test fixture
                evidence=(
                    EntityEvidence(kind="host", value="acme.example", source="zendesk"),
                    EntityEvidence(kind="legal_name", value="Acme Inc", source="zendesk"),
                ),
            ),
        ),
    )
    assert decision.status in {"created", "joined"}
    assert decision.entity is not None
    assert {b.system for b in decision.entity.bindings} == {"hubspot", "quickbooks", "zendesk"}

