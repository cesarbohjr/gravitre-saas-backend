"""Canonical durable step entrypoints for approved provider writes.

All execution runs under the prospect_play_runs state machine. The Play
service must authenticate actor/org membership before invoking this module.
"""
from __future__ import annotations
from typing import Any
from app.plays.prospecting_execution import run_stage
from app.plays.prospecting_approvals import bound_resolver
from app.plays.prospecting_smartlead_enrollment import enroll_approved_smartlead_lead

def run_smartlead_enrollment_stage(*,client:Any,settings:Any,org_id:str,
  run_id:str,actor_id:str,connector_id:str,campaign_id:str,
  prospect_contact_id:str,recipient_email:str,first_name:str="",
  last_name:str="")->dict[str,Any]:
    payload={"connector_id":connector_id,"campaign_id":campaign_id,
      "prospect_contact_id":prospect_contact_id,
      "recipient_email":recipient_email.strip().lower(),
      "first_name":first_name,"last_name":last_name}
    def write()->dict[str,Any]:
        return enroll_approved_smartlead_lead(client=client,settings=settings,
            org_id=org_id,run_id=run_id,actor_id=actor_id,**payload)
    return run_stage(client,org_id=org_id,run_id=run_id,actor_id=actor_id,
        stage="outreach_enroll",approval_resolver=bound_resolver(client,payload),
        execute=write)
