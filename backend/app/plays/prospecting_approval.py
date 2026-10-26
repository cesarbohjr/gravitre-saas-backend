"""Exact approval verification for prospecting writes.

The canonical PendingAction is represented in persisted conversation state,
but prospecting external writes additionally require an immutable, service-owned
approval grant bound to action and SHA-256 payload. No caller boolean accepted.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any

def payload_hash(payload:dict[str,Any])->str:
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def resolve_prospecting_approval(client:Any,*,org_id:str,actor_id:str,run_id:str,
                                stage:str,action:str,payload:dict[str,Any])->str|None:
    expected=payload_hash(payload)
    rows=(client.table("prospect_action_approvals")
          .select("id,status,action,payload_hash,actor_id,run_id,stage")
          .eq("org_id",org_id).eq("actor_id",actor_id).eq("run_id",run_id)
          .eq("stage",stage).eq("action",action).eq("payload_hash",expected)
          .eq("status","approved").limit(1).execute().data or [])
    if not rows: return None
    record=rows[0]
    if any(str(record.get(k)) != str(v) for k,v in {
        "actor_id":actor_id,"run_id":run_id,"stage":stage,"action":action,"payload_hash":expected}.items()):
        return None
    return str(record["id"])
