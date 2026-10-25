"""Deterministic, fail-closed admission policy for the Prospecting Play.

Company discovery and verification never constitute consent. This module is
pure so that canonical workflows and API endpoints share exactly one gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProspectDecision(StrEnum):
    QUARANTINE = "quarantine"
    REVIEW = "review"
    CRM_READY = "crm_ready"


@dataclass(frozen=True)
class ProspectEvidence:
    company_name: str
    company_domain: str
    company_source_url: str
    company_fit_score: int
    contact_name: str
    contact_role: str
    identity_source_url: str
    business_email: str
    email_domain: str
    verified_by: str
    verified_at: str
    consent_basis: str
    consent_source_url: str
    consent_reviewed_by: str
    consent_reviewed_at: str
    source_reuse_authorized: bool = False
    suppressed: bool = False
    verification_status: str = "unknown"


def prospect_admission(evidence: ProspectEvidence, *, minimum_score: int = 70) -> tuple[ProspectDecision, tuple[str, ...]]:
    errors: list[str] = []
    if not evidence.source_reuse_authorized:
        errors.append("source_usage_not_authorized")
    if not all((evidence.company_name, evidence.company_domain, evidence.company_source_url)):
        errors.append("company_evidence_missing")
    if not 0 <= evidence.company_fit_score <= 100 or evidence.company_fit_score < minimum_score:
        errors.append("company_below_threshold")
    if not all((evidence.contact_name, evidence.contact_role, evidence.identity_source_url)):
        errors.append("contact_identity_not_reviewable")
    local, separator, domain = evidence.business_email.strip().lower().rpartition("@")
    if not separator or not local or domain != evidence.company_domain.lower().removeprefix("www.") or domain != evidence.email_domain.lower():
        errors.append("business_email_domain_mismatch")
    if evidence.verification_status != "valid" or not evidence.verified_by or not evidence.verified_at:
        errors.append("email_not_verified")
    if not all((evidence.consent_basis, evidence.consent_source_url, evidence.consent_reviewed_by, evidence.consent_reviewed_at)):
        errors.append("consent_review_missing")
    if evidence.suppressed:
        errors.append("suppressed")
    if errors:
        decision = ProspectDecision.QUARANTINE if (
            "source_usage_not_authorized" in errors or "suppressed" in errors
        ) else ProspectDecision.REVIEW
        return decision, tuple(errors)
    return ProspectDecision.CRM_READY, ()


def crm_write_allowed(*, feature_flag: bool, approval_present: bool, decision: ProspectDecision) -> bool:
    """Still requires canonical PendingAction approval and scoped execution."""
    return bool(feature_flag and approval_present and decision == ProspectDecision.CRM_READY)
