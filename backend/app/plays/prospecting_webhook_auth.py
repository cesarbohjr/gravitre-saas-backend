"""Provider webhook admission; tenant is resolved from persisted provider lead map.

Signature scheme is configurable only for a verified HMAC-SHA256 webhook
installation. A provider without this documented signing contract must use a
trusted Nango poller instead (never mark unverified callbacks trusted).
"""
from __future__ import annotations
import hashlib
import hmac
from typing import Any
from app.plays.prospecting_delivery import record_delivery_event

def verify_hmac_sha256(body:bytes,signature:str,secret:str)->bool:
    if not secret or not signature or len(body)>1_000_000: return False
    supplied=signature.removeprefix("sha256=").strip().lower()
    expected=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied,expected)

def ingest_verified_event(client:Any,*,body:bytes,signature:str,secret:str,
       provider:str,event_id:str,lead_id:str,event_type:str)->dict[str,Any]:
    if not verify_hmac_sha256(body,signature,secret):
        raise PermissionError("Webhook signature verification failed")
    links=(client.table("prospect_outreach_lead_links").select("org_id")
      .eq("provider",provider).eq("provider_lead_id",lead_id).limit(2).execute().data or [])
    if len(links)!=1: raise PermissionError("Provider lead has no unique tenant mapping")
    return record_delivery_event(client,org_id=str(links[0]["org_id"]),
       provider=provider,event_id=event_id,event_type=event_type,
       provider_lead_id=lead_id,source_verified=True)
