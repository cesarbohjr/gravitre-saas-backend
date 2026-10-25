"""Durable, fail-closed step dispatcher for prospecting play execution.

A checkpoint is written before and after each operation. Review, CRM export
and sending are external approval boundaries; a retry never assumes success
from a timeout. Requires authenticated caller and service-role database client.
"""
from __future__ import annotations
from typing import Any, Callable

STAGES=("discover","research","enrich","verify","consent_review","stage")
APPROVAL_STAGES=frozenset({"consent_review","stage","crm_export","outreach_enroll"})

def run_stage(client:Any,*,org_id:str,run_id:str,stage:str,actor_id:str,
              execute:Callable[[],dict[str,Any]],
              approval_resolver:Callable[[str,str,str,str],bool]|None=None)->dict[str,Any]:
    if not all((org_id,run_id,actor_id)) or stage not in (*STAGES,"crm_export","outreach_enroll","delivery_sync"):
        raise ValueError("Tenant, run, actor and supported stage required")
    runs=(client.table("prospect_play_runs").select("id,state,current_stage").eq("org_id",org_id)
          .eq("id",run_id).limit(1).execute().data or [])
    if not runs or runs[0]["state"] in {"cancelled","failed","completed"}:
        raise PermissionError("Run missing or not executable")
    current=runs[0]["current_stage"]
    if current!=stage:
        raise PermissionError("Out of order stage execution")
    existing=(client.table("prospect_play_steps").select("status,evidence").eq("org_id",org_id)
              .eq("run_id",run_id).eq("stage",stage).limit(1).execute().data or [])
    if existing and existing[0]["status"]=="succeeded":
        return {"status":"succeeded","replayed":True,"evidence":existing[0]["evidence"]}
    if existing and existing[0]["status"] in {"running","outcome_unknown"}:
        return {"status":"outcome_unknown","replayed":True}
    # No caller-controlled approval flag: resolve authorization against trusted\n    # server-side PendingAction state for this tenant, actor, run and stage.\n    approved = False\n    if stage in APPROVAL_STAGES and approval_resolver is not None:\n        approved = approval_resolver(org_id, actor_id, run_id, stage) is True\n    if stage in APPROVAL_STAGES and not approved:
        client.table("prospect_play_steps").upsert({"org_id":org_id,"run_id":run_id,
           "stage":stage,"status":"awaiting_approval"},on_conflict="org_id,run_id,stage").execute()
        client.table("prospect_play_runs").update({"state":"awaiting_approval"}).eq("org_id",org_id).eq("id",run_id).execute()
        return {"status":"awaiting_approval"}
    claimed=client.rpc("prospect_claim_step",{
        "p_org":org_id,"p_run":run_id,"p_stage":stage,"p_actor":actor_id
    }).execute()
    if claimed.data is not True:
        return {"status":"concurrent_or_invalid_claim","stage":stage}
    try:
        evidence=execute()
        if not isinstance(evidence,dict) or evidence.get("success") is not True:
            raise RuntimeError("Stage did not confirm success")
    except Exception:
        client.table("prospect_play_steps").update({"status":"outcome_unknown",
           "last_error":"Execution failed; reconcile outcome before retry"}).eq("org_id",org_id).eq("run_id",run_id).eq("stage",stage).execute()
        raise
    client.table("prospect_play_steps").update({"status":"succeeded","evidence":evidence}).eq("org_id",org_id).eq("run_id",run_id).eq("stage",stage).execute()
    idx=STAGES.index(stage) if stage in STAGES else -1
    next_stage=STAGES[idx+1] if idx>=0 and idx+1<len(STAGES) else ("crm_export" if stage=="stage" else "outreach_enroll" if stage=="crm_export" else "delivery_sync" if stage=="outreach_enroll" else "completed")
    client.table("prospect_play_runs").update({"current_stage":next_stage,
        "state":"completed" if next_stage=="completed" else "running"}).eq("org_id",org_id).eq("id",run_id).execute()
    return {"status":"succeeded","stage":stage,"next_stage":next_stage,"evidence":evidence}
