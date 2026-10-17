#!/usr/bin/env python3
"""End-to-end revocation proof, strictly limited to the disposable smoke organization."""
import json, os, time, uuid, urllib.request, urllib.error
from pathlib import Path
from supabase import create_client

OUTPUT=Path("docs/delivery/release1-chat-voice-e2e.json")
def probe(path, payload, token, org, canary):
    req=urllib.request.Request("https://api.gravitre.app"+path,
        data=json.dumps(payload).encode(),method="POST",
        headers={"Authorization":"Bearer "+token,"x-org-id":org,
                 "Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=100) as response:
            data=response.read(2000000).decode("utf-8","replace")
            return {"http":response.status,"contains_canary":canary.lower() in data.lower()}
    except urllib.error.HTTPError as exc:
        return {"http":exc.code,"contains_canary":False}

def main():
    env=os.environ
    org=env["PLATFORM_LIVE_ORG_ID"]
    if env.get("PLATFORM_LIVE_AUTH_MODE")!="smoke_org_short_lived":
        raise RuntimeError("Isolated short-lived session missing")
    db=create_client(env["SUPABASE_URL"],env["SUPABASE_SERVICE_ROLE_KEY"])
    o=db.table("organizations").select("settings").eq("id",org).single().execute().data
    if (o.get("settings") or {}).get("isolated_conversation_test_org") is not True:
        raise RuntimeError("Refusing any non-isolated organization")
    token=env["PLATFORM_LIVE_BEARER_TOKEN"]
    marker=uuid.uuid4().hex
    canary="QBR"+marker[:12].upper()
    connector_id=memory_id=None
    results=[]
    def invoke(label):
        question="What is our quarterly business review codeword? Reply with only that codeword."
        cid=str(uuid.uuid4())
        if label=="chat":
            return probe("/api/assistant/chat",
                {"messages":[{"role":"user","content":question}],
                 "conversation_id":cid,"org_id":org,"tools":[]},token,org,canary)
        return probe("/api/voice/session/turn",
            {"text":question,"conversation_id":cid,"turn_id":str(uuid.uuid4())},token,org,canary)
    try:
        connector=db.table("connectors").insert({"org_id":org,"name":"security-probe-"+marker,
             "type":"custom","environment":"production","status":"connected"}).execute().data
        connector_id=connector[0]["id"]
        memories=db.table("agent_memories").insert({"org_id":org,
            "content":"Quarterly business review codeword: "+canary,
            "category":"decision","source_connector_id":connector_id,
            "source_class":"user_direct","is_active":True,
            "provenance":"release1_isolated_e2e"}).execute().data
        memory_id=memories[0]["id"]
        time.sleep(3)
        for surface in ("chat","voice"):
            p=invoke(surface)
            results.append({"name":surface+"_before","pass":p["http"]==200 and p["contains_canary"],"http":p["http"]})
        db.table("connectors").update({"status":"disconnected"}).eq("id",connector_id).eq("org_id",org).execute()
        for surface in ("chat","voice"):
            p=invoke(surface)
            results.append({"name":surface+"_after","pass":p["http"]==200 and not p["contains_canary"],"http":p["http"]})
    finally:
        if memory_id:
            db.table("agent_memories").delete().eq("id",memory_id).eq("org_id",org).execute()
        if connector_id:
            db.table("connectors").delete().eq("id",connector_id).eq("org_id",org).execute()
    verdict="PASS" if len(results)==4 and all(r["pass"] for r in results) else "FAIL"
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps({"verdict":verdict,"results":results,
       "scope":"isolated_smoke_org","limitations":["text-ingress voice turn, not microphone capture",
       "canary exact-match, not paraphrase or other-source cache sweep"]},indent=2)+"\n")
    print(json.dumps({"verdict":verdict,"results":results}))
    return 0 if verdict=="PASS" else 1

if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        print("REVOKE_E2E_ERROR:"+type(exc).__name__+" code="+str(getattr(exc,"code","unknown")))
        raise SystemExit(2)
