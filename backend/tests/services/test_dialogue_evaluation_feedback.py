"""Canonical LEARN feedback with real filters and no extra authority."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app.services.cognitive_turn_kernel import CognitiveTurnKernel,CognitiveTurnRequest,CognitiveTurnContext,StageRecord
from app.services.dialogue_evaluation_feedback import EVENT,feedback_summary,record_turn_feedback,purge_feedback
from tests.support.fake_supabase import FakeSupabase, FakeQuery, FakeResponse

class Query(FakeQuery):
    def delete(self):
        self.op="delete"
        return self
    def lt(self,column,value):
        self.range_filter=(column,value,"lt")
        return self
    def gte(self,column,value):
        self.range_filter=(column,value,"gte")
        return self
    def _matches(self,row):
        if hasattr(self,"range_filter"):
            column,value,op=self.range_filter
            if op=="lt" and str(row.get(column,""))>=value:return False
            if op=="gte" and str(row.get(column,""))<value:return False
        return super()._matches(row)
    def execute(self):
        if self.op=="delete":
            rows=self.client.tables.setdefault(self.table,[])
            removed=[r for r in rows if self._matches(r)]
            rows[:]=[r for r in rows if not self._matches(r)]
            return FakeResponse(removed)
        return super().execute()

class DB(FakeSupabase):
    def table(self,name):return Query(self,name)

def request(db,spoken=False,org="org-a"):
    return CognitiveTurnRequest(org_id=org,user_id="user-a",client=db,spoken_mode=spoken,message="SECRET TRANSCRIPT")
def context():
    return CognitiveTurnContext(turn_id="turn-a",stages=[StageRecord("PLAN",True,12.5),StageRecord("GOVERN",True,3)])
@pytest.fixture
def db():
    client=DB()
    client.tables={"org_intelligence_engine_settings":[{"org_id":"org-a","dialogue_settings":{"evaluation_feedback_enabled":True}},{"org_id":"org-b","dialogue_settings":{"evaluation_feedback_enabled":False}}]}
    return client

@pytest.mark.asyncio
async def test_kernel_learn_receipt_idempotency_and_no_business_success(db,monkeypatch):
    kernel=CognitiveTurnKernel(SimpleNamespace(dialogue_memory_governance_v1=False))
    monkeypatch.setattr(kernel,"_persist_trace",AsyncMock())
    req=request(db); ctx=context()
    result=await kernel.run_learn(req,ctx,act_result={"status":"completed","response":"PRIVATE RESPONSE"})
    assert result.learn["evaluation_feedback"]["status"]=="recorded"
    await kernel.run_learn(req,ctx)
    rows=db.tables["intelligence_outcome_events"]
    assert len(rows)==1 and rows[0]["outcome_event"]==EVENT
    assert rows[0]["metadata"]["quality_judged"] is False
    assert "SECRET" not in repr(rows) and "PRIVATE" not in repr(rows)
    from app.services.cognitive_outcome_loop import bias_notes_from_event_rows
    assert bias_notes_from_event_rows(rows,"anything")["weight_delta"]==0

@pytest.mark.asyncio
async def test_consent_scope_channel_parity_and_erasure(db):
    assert (await record_turn_feedback(request(db,org="org-b"),context(),object()))["status"]=="disabled"
    assert (await record_turn_feedback(request(db),context(),object()))["status"]=="recorded"
    voice=context(); voice.turn_id="voice-a"
    assert (await record_turn_feedback(request(db,True),voice,object()))["status"]=="recorded"
    result=feedback_summary(db,"org-a")
    assert result["channels"]["text"]["turns"]==result["channels"]["voice"]["turns"]==1
    assert feedback_summary(db,"org-b")["channels"]["voice"]["turns"]==0
    assert result["automatic_promotion"] is False
    purge_feedback(db,"org-b"); assert len(db.tables["intelligence_outcome_events"])==2
    purge_feedback(db,"org-a"); assert not db.tables["intelligence_outcome_events"]

@pytest.mark.asyncio
async def test_missing_readback_and_invalid_retention(db,monkeypatch):
    import app.services.dialogue_evaluation_feedback as feedback
    monkeypatch.setattr(feedback,"_read",lambda *a:[])
    assert (await feedback.record_turn_feedback(request(db),context(),object()))["status"]=="unverified"
    db.tables["org_intelligence_engine_settings"][0]["dialogue_settings"]["evaluation_feedback_retention_days"]=-1
    assert (await feedback.record_turn_feedback(request(db),context(),object()))["status"]=="invalid_retention"

@pytest.mark.asyncio
async def test_speculative_feedback_is_deferred_until_adoption(db,monkeypatch):
    from app.services import speculative_execution
    pending=[]; scope=SimpleNamespace(defer=lambda label,callback:pending.append((label,callback)))
    monkeypatch.setattr(speculative_execution,"current_scope",lambda:scope)
    result=await CognitiveTurnKernel(SimpleNamespace()).run_learn(request(db),context())
    assert result.learn["deferred"]=="speculative"
    assert "intelligence_outcome_events" not in db.tables and len(pending)==1

@pytest.mark.asyncio
async def test_retention_erases_only_expired_matching_tenant_evaluations(db):
    from datetime import datetime,timedelta,timezone
    old=(datetime.now(timezone.utc)-timedelta(days=60)).isoformat()
    db.tables["intelligence_outcome_events"]=[
        {"id":"expired","org_id":"org-a","outcome_event":EVENT,"created_at":old},
        {"id":"foreign","org_id":"org-b","outcome_event":EVENT,"created_at":old},
        {"id":"business","org_id":"org-a","outcome_event":"business_metric_improved","created_at":old},
    ]
    assert (await record_turn_feedback(request(db),context(),object()))["status"]=="recorded"
    assert {r["id"] for r in db.tables["intelligence_outcome_events"]}>={"foreign","business"}
    assert not db.rows("intelligence_outcome_events",id="expired")

@pytest.mark.asyncio
async def test_existing_receipt_mismatch_is_not_overwritten_or_reported_success(db):
    assert (await record_turn_feedback(request(db),context(),object()))["status"]=="recorded"
    db.tables["intelligence_outcome_events"][0]["metadata"]["duration_ms"]=999
    assert (await record_turn_feedback(request(db),context(),object()))["status"]=="receipt_mismatch"
    assert len(db.tables["intelligence_outcome_events"])==1

@pytest.mark.asyncio
@pytest.mark.parametrize("update",[{"evaluation_feedback_enabled":"true"},{"evaluation_feedback_retention_days":True},{"evaluation_feedback_retention_days":91}])
async def test_invalid_admin_settings_fail_before_write(db,update):
    from app.services.chat_dialogue_settings import save_chat_dialogue_settings
    with pytest.raises(ValueError):
        await save_chat_dialogue_settings("org-a",update,settings=object(),client=db)
    assert not db.log


@pytest.mark.parametrize("value",["true",1,[],{}])
def test_admin_api_does_not_coerce_feedback_consent(value):
    from app.routers.admin_chat import DialogueSettingsUpdate
    with pytest.raises(ValueError):
        DialogueSettingsUpdate(evaluation_feedback_enabled=value)

@pytest.mark.asyncio
async def test_metrics_review_route_requires_admin_and_keeps_tenant_scope(db,monkeypatch,mock_settings):
    from fastapi import FastAPI,HTTPException
    from httpx import ASGITransport,AsyncClient
    from app.routers import admin_chat
    from app.auth.dependencies import require_admin,get_org_context
    from app.config import get_settings
    async def load(org_id,settings):
        return {"evaluation_feedback_enabled":True,"evaluation_feedback_retention_days":30}
    monkeypatch.setattr(admin_chat,"load_chat_dialogue_settings",load)
    monkeypatch.setattr(admin_chat,"get_supabase_client",lambda settings:db)
    assert (await record_turn_feedback(request(db),context(),mock_settings))["status"]=="recorded"
    app=FastAPI();app.include_router(admin_chat.router)
    app.dependency_overrides[get_org_context]=lambda:"org-a"
    app.dependency_overrides[get_settings]=lambda:mock_settings
    def denied():raise HTTPException(status_code=403,detail="admin_required")
    app.dependency_overrides[require_admin]=denied
    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://local") as client:
        assert (await client.get("/api/admin/chat/evaluation-feedback")).status_code==403
        app.dependency_overrides[require_admin]=lambda:("org-a","admin")
        result=await client.get("/api/admin/chat/evaluation-feedback")
        assert result.status_code==200 and result.json()["status"]=="available"
        assert result.json()["channels"]["text"]["turns"]==1
        assert result.json()["automatic_promotion"] is False
        app.dependency_overrides[get_org_context]=lambda:"org-b"
        assert (await client.get("/api/admin/chat/evaluation-feedback")).json()["channels"]["text"]["turns"]==0


def test_erasure_without_readback_cannot_be_reported_complete(db,monkeypatch):
    original=Query.execute
    def ignore_delete(self):
        return FakeResponse([]) if self.op=="delete" else original(self)
    monkeypatch.setattr(Query,"execute",ignore_delete)
    db.tables["intelligence_outcome_events"]=[{"id":"retained","org_id":"org-a","outcome_event":EVENT}]
    with pytest.raises(ValueError,match="erasure_unverified"):
        purge_feedback(db,"org-a")


@pytest.mark.asyncio
async def test_same_turn_id_in_two_agents_cannot_reuse_each_others_receipt(db):
    a=request(db);a.agent_id="agent-a"
    b=request(db);b.agent_id="agent-b"
    first=await record_turn_feedback(a,context(),object())
    second=await record_turn_feedback(b,context(),object())
    assert first["status"]==second["status"]=="recorded"
    assert first["receipt_id"]!=second["receipt_id"]
    assert {r["agent_id"] for r in db.tables["intelligence_outcome_events"]}=={"agent-a","agent-b"}
