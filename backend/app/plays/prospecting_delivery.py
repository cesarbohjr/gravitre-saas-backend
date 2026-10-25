"""Validated delivery events for Nango-connected outbound providers.

Transport webhook signature verification belongs to the authenticated router
before this function. A provider lead ID must be mapped to org-owned records
on the server; callers may not select org from untrusted webhook JSON.
"""
from __future__ import annotations
from typing import Any

EVENT_TYPES=frozenset({"sent","delivered","bounced","replied","unsubscribed","complained","failed"})
SUPPRESS_TYPES=frozenset({"bounced","unsubscribed","complained"})

def record_delivery_event(client:Any,*,org_id:str,provider:str,event_id:str,
                          event_type:str,provider_lead_id:str,
                          source_verified:bool,recipient_email:str|None=None)->dict[str,Any]:
    if not source_verified:
        raise PermissionError("Verified webhook signature or trusted provider poll required")
    if not all((org_id,provider,event_id,provider_lead_id)) or event_type not in EVENT_TYPES:
        raise ValueError("Validated tenant, event and lead mapping required")
    row=(client.table("prospect_outreach_events").select("id").eq("org_id",org_id)
         .eq("provider",provider).eq("provider_event_id",event_id).limit(1).execute().data or [])
    if row:
        return {"recorded":False,"duplicate":True,"event_type":event_type}
    result=(client.table("prospect_outreach_events").insert({"org_id":org_id,
       "provider":provider,"provider_event_id":event_id,
       "provider_lead_id":provider_lead_id,"event_type":event_type}).execute().data or [])
    if not result:
        raise RuntimeError("Event persistence failed")
    if event_type in SUPPRESS_TYPES:
        if not recipient_email:
            # Do not mark synchronized: suppression MUST succeed before campaign continuation.
            raise RuntimeError("Recipient mapping unavailable; outbound campaign must pause")
        email=recipient_email.strip().lower()
        if "@" not in email:
            raise RuntimeError("Invalid recipient mapping; campaign must pause")
        client.table("prospect_suppressions").upsert({
          "org_id":org_id,"normalized_email":email,"reason":event_type
        },on_conflict="org_id,normalized_email").execute()
    return {"recorded":True,"duplicate":False,"event_type":event_type,
      "suppression_applied":event_type in SUPPRESS_TYPES}
