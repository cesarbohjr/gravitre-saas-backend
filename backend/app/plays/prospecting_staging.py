"""Server-side staging gate for native Prospecting Play.

Only persisted source-of-record fields are evaluated; caller cannot submit a
fabricated consent/verification object. Staging creates no external CRM record.
"""
from __future__ import annotations
from typing import Any
from app.plays.prospecting_policy import ProspectEvidence,ProspectDecision,prospect_admission

def stage_reviewed_contact(client:Any,*,org_id:str,contact_id:str,actor_id:str)->dict[str,Any]:
    if not all((org_id,contact_id,actor_id)):
        raise ValueError("Authenticated tenant, contact and actor required")
    rows=(client.table("prospect_contacts").select("*").eq("org_id",org_id)
          .eq("id",contact_id).limit(1).execute().data or [])
    if not rows: raise LookupError("Contact not found")
    contact=rows[0]
    companies=(client.table("prospect_companies").select("*").eq("org_id",org_id)
               .eq("id",contact["company_id"]).limit(1).execute().data or [])
    if not companies: raise LookupError("Company not found in organization")
    company=companies[0]
    email=str(contact.get("email") or "").strip().lower()
    suppressed=(client.table("prospect_suppressions").select("id").eq("org_id",org_id)
                .eq("normalized_email",email).limit(1).execute().data or [])
    evidence=ProspectEvidence(
        company_name=str(company.get("name") or ""),
        company_domain=str(company.get("domain") or ""),
        company_source_url=str(company.get("source_url") or ""),
        company_fit_score=int(company.get("fit_score") or 0),
        contact_name=str(contact.get("full_name") or ""),
        contact_role=str(contact.get("role_title") or ""),
        identity_source_url=str(contact.get("identity_source_url") or ""),
        business_email=email,
        email_domain=email.partition("@")[2],
        verified_by=str(contact.get("verification_provider") or ""),
        verified_at=str(contact.get("verified_at") or ""),
        verification_status=str(contact.get("email_status") or "unknown"),
        consent_basis=str(contact.get("consent_basis") or ""),
        consent_source_url=str(contact.get("consent_source_url") or ""),
        consent_reviewed_by=str(contact.get("consent_reviewed_by") or ""),
        consent_reviewed_at=str(contact.get("consent_reviewed_at") or ""),
        source_reuse_authorized=company.get("source_authorized") is True,
        suppressed=bool(contact.get("suppressed") or suppressed),
    )
    decision,blockers=prospect_admission(evidence)
    if decision!=ProspectDecision.CRM_READY:
        return {"staged":False,"blockers":list(blockers),"sent":False,"crm_written":False}
    row=(client.table("prospect_staging").upsert({
        "org_id":org_id,"contact_id":contact_id,"requested_by":actor_id,
        "status":"pending_approval",
    },on_conflict="org_id,contact_id").execute().data or [])
    if not row: raise RuntimeError("Staging insert failed")
    return {"staged":True,"staging_id":row[0]["id"],
            "status":"pending_approval","sent":False,"crm_written":False}
