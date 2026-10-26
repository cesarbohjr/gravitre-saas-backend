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
    if event_type in SUPPRESS_TYPES and (not recipient_email or "@" not in recipient_email):
        raise ValueError("Recipient required to apply suppression atomically")
    result=client.rpc("prospect_record_delivery_atomic",{
        "p_org":org_id,"p_provider":provider,"p_event_id":event_id,
        "p_lead":provider_lead_id,"p_event_type":event_type,
        "p_email":(recipient_email or "").strip().lower()
    }).execute()
    if result.data is not True and result.data is not False:
        raise RuntimeError("Atomic delivery persistence not confirmed")
    return {"recorded":result.data is True,"duplicate":result.data is False,
       "event_type":event_type,"suppression_applied":result.data is True and event_type in SUPPRESS_TYPES}
