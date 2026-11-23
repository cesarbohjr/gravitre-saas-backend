"""Real mutation/cache helpers with synthetic storage; not Redis/deployed proof."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import agent_memory_service as memory
from app.services import cache_service, memory_lifecycle_service as lifecycle
from app.services import memory_source_liveness as liveness
from app.services import memory_temporal_service as temporal, tier0_cache as tier0

ORG, OTHER, AGENT, MID = "org-a", "org-b", "agent-a", "memory-a"
QUERY = "What is our support policy?"


class Query:
    def __init__(self, db, table):
        self.db,self.table,self.filters,self.action,self.payload=db,table,[],None,None
    def select(self,*_args):return self
    def eq(self,key,value):self.filters.append((key,value));return self
    def limit(self,*_args):return self
    def order(self,*_args,**_kwargs):return self
    def update(self,payload):self.action,self.payload="update",payload;return self
    def delete(self):self.action="delete";return self
    def insert(self,payload):self.action,self.payload="insert",payload;return self
    def execute(self):
        if self.action and self.db.fail_writes:raise PermissionError("synthetic write denial")
        table=self.db.tables.setdefault(self.table,[])
        rows=[r for r in table if all(r.get(k)==v for k,v in self.filters)]
        if self.action=="delete":
            self.db.tables[self.table]=[r for r in table if r not in rows]
        elif self.action=="update":
            for r in rows:r.update(self.payload)
        elif self.action=="insert":
            row={"id":f"insert-{len(table)}",**deepcopy(self.payload)}
            table.append(row);rows=[row]
        return SimpleNamespace(data=deepcopy(rows))


class DB:
    def __init__(self):
        self.fail_writes=False
        self.tables={
            "agents":[{"id":AGENT,"org_id":ORG,"name":"Synthetic"}],
            "agent_memories":[{"id":MID,"org_id":ORG,"agent_id":AGENT,
                "content":"Support policy: old value","category":"preference","confidence":90,
                "editable":True,"is_active":True,"is_current":True,"memory_key":"preference:policy"}],
        }
    def table(self,name):return Query(self,name)


@pytest.fixture
def cache(monkeypatch,mock_settings):
    monkeypatch.setattr(cache_service,"_MEMORY",{})
    monkeypatch.setattr(cache_service,"_MEMORY_STATS",{})
    monkeypatch.setattr(cache_service,"get_redis_client",lambda _settings:None)
    cache=cache_service.CacheService(mock_settings)
    monkeypatch.setattr(cache_service,"get_cache_service",lambda settings=None:cache)
    monkeypatch.setattr(tier0,"get_cache_service",lambda settings=None:cache)
    monkeypatch.setattr(memory,"get_embedding",lambda *_args,**_kwargs:[0.1])
    return cache


async def seed(settings,org=ORG):
    await tier0.set_tier0_answer(settings,org_id=org,query=QUERY,
                                answer="Support policy: old value",source_document_ids=[])
    assert await tier0.get_tier0_answer(settings,org_id=org,query=QUERY)


def mutate(kind,settings,db):
    if kind=="delete":memory.delete_agent_memory(db,ORG,AGENT,MID)
    elif kind=="deactivate":assert lifecycle.deactivate_memory(db,org_id=ORG,memory_id=MID,reason="explicit forget")
    elif kind=="update":memory.update_agent_memory(settings,db,ORG,AGENT,MID,content="Support policy: new value")
    elif kind=="create":memory.create_agent_memory(settings,db,ORG,AGENT,user_id="user-a",
                                                    content="New policy",share_with_department=False)
    else:
        row=temporal.upsert_temporal_memory(db,{"org_id":ORG,"agent_id":AGENT,"category":"preference",
            "content":"Support policy: new value","memory_key":"preference:policy" if kind=="supersede" else "preference:new"})
        assert row


@pytest.mark.asyncio
@pytest.mark.parametrize("kind",["delete","deactivate","update","create","supersede","temporal_insert"])
async def test_successful_memory_mutation_invalidates_only_its_org(cache,mock_settings,kind):
    await seed(mock_settings)
    await seed(mock_settings,OTHER)
    before=liveness.epoch_parts(ORG,mock_settings)
    db=DB();before_rows=deepcopy(db.tables)
    mutate(kind,mock_settings,db)
    assert db.tables!=before_rows
    assert await tier0.get_tier0_answer(mock_settings,org_id=ORG,query=QUERY) is None
    assert liveness.epoch_parts(ORG,mock_settings)!=before
    assert (await tier0.get_tier0_answer(mock_settings,org_id=OTHER,query=QUERY))["answer"]=="Support policy: old value"


@pytest.mark.asyncio
async def test_epoch_change_during_cache_read_does_not_return_stale_answer(cache,mock_settings,monkeypatch):
    await seed(mock_settings)
    original=cache.get
    async def get(namespace,*parts):
        result=await original(namespace,*parts)
        if namespace=="tier0_answer":liveness.invalidate_org_retrieval_cache(ORG,reason="synthetic concurrent mutation")
        return result
    monkeypatch.setattr(cache,"get",get)
    assert await tier0.get_tier0_answer(mock_settings,org_id=ORG,query=QUERY) is None


@pytest.mark.asyncio
async def test_epoch_change_during_fill_does_not_store_old_answer_in_new_epoch(cache,mock_settings,monkeypatch):
    async def fingerprint(*_args):
        liveness.invalidate_org_retrieval_cache(ORG,reason="synthetic mutation during fill")
        return ""
    monkeypatch.setattr(tier0,"_source_fingerprint",fingerprint)
    await tier0.set_tier0_answer(mock_settings,org_id=ORG,query=QUERY,
                                answer="old context",source_document_ids=[])
    assert await tier0.get_tier0_answer(mock_settings,org_id=ORG,query=QUERY) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("kind",["delete","deactivate","update","create","supersede","temporal_insert"])
async def test_failed_mutation_does_not_invalidate_unchanged_memory(cache,mock_settings,kind):
    await seed(mock_settings)
    db=DB();db.fail_writes=True
    before=liveness.epoch_parts(ORG,mock_settings)
    if kind=="deactivate":
        assert lifecycle.deactivate_memory(db,org_id=ORG,memory_id=MID,reason="explicit forget") is False
    elif kind in {"supersede","temporal_insert"}:
        assert temporal.upsert_temporal_memory(db,{"org_id":ORG,"category":"preference",
            "content":"new value","memory_key":"preference:policy" if kind=="supersede" else "preference:new"}) is None
    else:
        with pytest.raises(PermissionError):mutate(kind,mock_settings,db)
    assert liveness.epoch_parts(ORG,mock_settings)==before
    assert await tier0.get_tier0_answer(mock_settings,org_id=ORG,query=QUERY)


@pytest.mark.asyncio
async def test_late_generation_fill_uses_its_original_epoch(cache,mock_settings):
    original=liveness.epoch_parts(ORG,mock_settings)
    mutate("delete",mock_settings,DB())
    await tier0.set_tier0_answer(mock_settings,org_id=ORG,query=QUERY,
        answer="old generation",source_document_ids=[],source_epoch=original)
    assert await tier0.get_tier0_answer(mock_settings,org_id=ORG,query=QUERY) is None
    fresh=liveness.epoch_parts(ORG,mock_settings)
    await tier0.set_tier0_answer(mock_settings,org_id=ORG,query=QUERY,
        answer="new generation",source_document_ids=[],source_epoch=fresh)
    assert (await tier0.get_tier0_answer(mock_settings,org_id=ORG,query=QUERY))["answer"]=="new generation"


@pytest.mark.asyncio
async def test_equivalent_temporal_memory_is_not_a_mutation(cache,mock_settings):
    await seed(mock_settings)
    before=liveness.epoch_parts(ORG,mock_settings)
    db=DB();row=deepcopy(db.tables['agent_memories'][0])
    assert temporal.upsert_temporal_memory(db,row)==row
    assert liveness.epoch_parts(ORG,mock_settings)==before
    assert await tier0.get_tier0_answer(mock_settings,org_id=ORG,query=QUERY)


@pytest.mark.asyncio
async def test_protected_memory_delete_does_not_invalidate(cache,mock_settings):
    from fastapi import HTTPException
    await seed(mock_settings)
    db=DB();db.tables['agent_memories'][0]['editable']=False
    with pytest.raises(HTTPException) as error:memory.delete_agent_memory(db,ORG,AGENT,MID)
    assert error.value.status_code==403
    assert liveness.epoch_parts(ORG,mock_settings)==()
    assert await tier0.get_tier0_answer(mock_settings,org_id=ORG,query=QUERY)


@pytest.mark.asyncio
async def test_actual_streaming_caller_fences_cache_fill_after_context_change(cache,mock_settings):
    from app.operators.react_engine import ReActResult, ReActStatus
    from tests.operators.test_typed_live_streaming import _run_typed_turn

    query="Explain a synthetic support policy in two sentences."
    original=liveness.epoch_parts("org-1",mock_settings)
    async def live(**_kwargs):return None
    async def react(**_kwargs):
        liveness.invalidate_org_retrieval_cache("org-1",reason="synthetic mutation during generation")
        yield SimpleNamespace(kind="done",react_result=ReActResult(
            status=ReActStatus.COMPLETED,answer="Synthetic old-context answer."))
    write=AsyncMock(side_effect=tier0.set_tier0_answer)
    with (
        patch("app.operators.agent_intelligence.tier0_enabled",return_value=True),
        patch("app.operators.agent_intelligence.set_tier0_answer",write),
        patch("app.services.context_compiler.compile_unified_reasoning_context",AsyncMock(
            return_value=SimpleNamespace(to_trace_dict=lambda:{}))),
    ):
        await _run_typed_turn(live,query=query,react_runner=react,requested_tools=[])
    write.assert_awaited_once()
    assert write.await_args.kwargs['source_epoch']==original
    assert await tier0.get_tier0_answer(mock_settings,org_id="org-1",query=query) is None
