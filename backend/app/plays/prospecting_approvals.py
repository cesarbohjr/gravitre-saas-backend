"""Approval resolver bound to exact tenant, actor, run, stage and immutable payload."""
from __future__ import annotations
import hashlib
import json
from typing import Any

def payload_digest(payload:dict[str,Any])->str:
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def resolve_stage_approval(client:Any,*,org_id:str,run_id:str,stage:str,
                           actor_id:str,approved_payload:dict[str,Any])->bool:
    if not all((org_id,run_id,stage,actor_id)):
        return False
    if stage not in {"consent_review","stage","crm_export","outreach_enroll"}:
        return False
    try:
        result=client.rpc("prospect_stage_approval_verified",{
           "p_org":org_id,"p_run":run_id,"p_stage":stage,
           "p_actor":actor_id,"p_digest":payload_digest(approved_payload),
        }).execute()
        return result.data is True
    except Exception:
        return False

def bound_resolver(client:Any,payload:dict[str,Any]):
    def check(org_id:str,actor_id:str,run_id:str,stage:str)->bool:
        return resolve_stage_approval(client,org_id=org_id,actor_id=actor_id,
            run_id=run_id,stage=stage,approved_payload=payload)
    return check
