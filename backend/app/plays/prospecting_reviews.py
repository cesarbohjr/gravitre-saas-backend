"""Persisted Prospecting Play review queue.

All data access is tenant-filtered; endorsement is not an outreach approval.
The database service role is used by the backend only, never browser clients.
"""
from __future__ import annotations

from typing import Any
from app.plays.prospecting_policy import ProspectEvidence, ProspectDecision, prospect_admission


def list_reviews(client: Any, org_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    if not org_id:
        raise ValueError("Organization context required")
    result = (
        client.table("prospect_contacts")
        .select("id,org_id,company_id,full_name,role_title,email,email_status,crm_status,identity_source_url,consent_basis,consent_source_url,suppressed,verified_at,verification_provider")
        .eq("org_id", org_id)
        .in_("crm_status", ["quarantine", "review", "eligible"])
        .limit(max(1, min(limit, 100)))
        .execute()
    )
    return [dict(row) for row in (result.data or [])]


def evaluate_and_record(client: Any, org_id: str, contact_id: str,
                        evidence: ProspectEvidence, *, reviewer_id: str) -> dict[str, Any]:
    if not org_id or not contact_id or not reviewer_id:
        raise ValueError("Organization, contact, and authenticated reviewer required")
    # Do not permit client-generated evidence to bypass source-of-record checks.
    company = (client.table("prospect_contacts").select("id,company_id,crm_status")
               .eq("org_id",org_id).eq("id",contact_id).limit(1).execute().data or [])
    if not company:
        raise LookupError("Contact not found for organization")
    decision, reasons = prospect_admission(evidence)
    state = "eligible" if decision == ProspectDecision.CRM_READY else (
        "quarantine" if decision == ProspectDecision.QUARANTINE else "review"
    )
    # This status never triggers a CRM write. Canonical PendingAction is required
    # and the separate outbound-send feature remains disabled.
    result = (client.table("prospect_contacts").update({
        "crm_status":state,
        "consent_reviewed_by":reviewer_id if evidence.consent_basis else None,
        "consent_reviewed_at":evidence.consent_reviewed_at if evidence.consent_basis else None,
    }).eq("org_id",org_id).eq("id",contact_id).execute())
    if not result.data:
        raise RuntimeError("Review write failed")
    return {"contact_id":contact_id,"state":state,"blockers":list(reasons),
            "crm_write_performed":False,"email_sent":False}
