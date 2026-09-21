"""Canonical Gravitre internal E2E tenant — isolated org, never customer.

Does not mint OAuth tokens. Does not impersonate Cesar. Test data only.
"""
from __future__ import annotations

from typing import Any

from app.services.business_entity_fabric import (
    BusinessEntity,
    EntityBinding,
    EntityEvidence,
    fold_company_bindings,
)
from app.services.conversation_write_guard import (
    DEFAULT_ISOLATED_CONVERSATION_TEST_EMAIL,
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
    ISOLATED_CONVERSATION_TEST_ORG_NAME,
    ISOLATED_CONVERSATION_TEST_ORG_SLUG,
    isolated_conversation_test_org_id,
)

E2E_ORG_ID = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
E2E_USER_ID = DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID
E2E_EMAIL = DEFAULT_ISOLATED_CONVERSATION_TEST_EMAIL
E2E_PURPOSE = "internal_e2e_2_0_acceptance_never_customer_visible"
TEST_COMPANY_HOST = "alpha.test.gravitre.app"
TEST_COMPANY_NAME = "Gravitre Test Customer Alpha"
TEST_COMPANY_EMAIL = "ops@alpha.test.gravitre.app"
ALPHA_ENTITY_ID = "a1fa0000-1501-4000-8000-c04e57a00001"


def e2e_org_policy() -> dict[str, Any]:
    return {
        "org_id": isolated_conversation_test_org_id() or E2E_ORG_ID,
        "name": ISOLATED_CONVERSATION_TEST_ORG_NAME,
        "slug": ISOLATED_CONVERSATION_TEST_ORG_SLUG,
        "purpose": E2E_PURPOSE,
        "never_customer_visible": True,
        "forbidden_operator_org": FORBIDDEN_OPERATOR_ORG_ID,
        "identities": [
            {
                "user_id": E2E_USER_ID,
                "email": E2E_EMAIL,
                "role": "conversation_smoke_sa",
            }
        ],
        "providers_desired": [
            "hubspot",
            "google_analytics",
            "google_search_console",
            "gmail",
            "quickbooks",
            "zendesk",
        ],
        "test_data_policy": "synthetic Gravitre Test Customer Alpha only; no customer PII",
        "cleanup_policy": "conversation rows owned by smoke SA; no operator-org writes",
    }


def test_customer_alpha_bindings() -> tuple[EntityBinding, ...]:
    host = EntityEvidence(kind="host", value=TEST_COMPANY_HOST, source="e2e_fixture")
    email = EntityEvidence(kind="email", value=TEST_COMPANY_EMAIL, source="e2e_fixture")
    name_hs = EntityEvidence(kind="legal_name", value="Gravitre Test Customer Alpha", source="hubspot")
    name_qbo = EntityEvidence(kind="legal_name", value="Gravitre Test Customer Alpha LLC", source="quickbooks")
    name_zd = EntityEvidence(kind="legal_name", value="Gravitre Test Cust. Alpha", source="zendesk")
    return (
        EntityBinding(
            system="hubspot",
            resource_type="company",
            resource_id="hs-alpha-test",
            confidence=0.92,
            evidence=(host, email, name_hs),
        ),
        EntityBinding(
            system="quickbooks",
            resource_type="customer",
            resource_id="qbo-alpha-test",
            confidence=0.91,
            evidence=(host, email, name_qbo),
        ),
        EntityBinding(
            system="zendesk",
            resource_type="organization",
            resource_id="zd-alpha-test",
            confidence=0.9,
            evidence=(host, email, name_zd),
        ),
    )


def seed_test_customer_alpha(*, org_id: str | None = None) -> BusinessEntity:
    decision = fold_company_bindings(
        org_id=org_id or E2E_ORG_ID,
        display_name=TEST_COMPANY_NAME,
        bindings=test_customer_alpha_bindings(),
    )
    if decision.entity is None:
        raise AssertionError(f"E2E Alpha join refused: {decision.status} {decision.reason}")
    entity = decision.entity
    return BusinessEntity(
        id=ALPHA_ENTITY_ID,
        org_id=entity.org_id,
        display_name=entity.display_name,
        kind=entity.kind,
        bindings=entity.bindings,
        evidence=entity.evidence,
        confidence=entity.confidence,
    )
