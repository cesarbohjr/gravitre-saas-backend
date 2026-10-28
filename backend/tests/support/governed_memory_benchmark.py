"""Synthetic storage/retriever fixtures around the real governed cognitive kernel.

No candidate SDK, embedding provider or production database is initialized.
The kernel, membership/consent decisions, liveness, contamination and promotion
code are production code; only external storage/retrieval/trace dependencies vary.
"""
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tests.support.fake_supabase import FakeQuery, FakeSupabase

ANCHOR = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return ANCHOR if tz else ANCHOR.replace(tzinfo=None)


class Query(FakeQuery):
    def in_(self, column, values):
        self.in_filter = (column, values)
        return self

    def _matches(self, row):
        if hasattr(self, "in_filter") and row.get(self.in_filter[0]) not in self.in_filter[1]:
            return False
        return super()._matches(row)


class DB(FakeSupabase):
    def table(self, name):
        return Query(self, name)


async def execute_case(case, *, retrieval="canonical_fixture", candidate_backend=None):
    if retrieval not in ("canonical_fixture", "mem0_contract_replay"):
        raise ValueError("Unknown research retrieval mode")
    if retrieval == "mem0_contract_replay" and case.get("operation") == "learn":
        raise ValueError("Search replay cannot certify candidate learning")
    from app.services.cognitive_turn_kernel import CognitiveTurnKernel, CognitiveTurnRequest, CognitiveTurnContext

    db = DB()
    policy = deepcopy(case.get("policy", {"recallEnabled": True, "learnEnabled": True, "retentionDays": 7}))
    db.tables["organizations"] = [{"id": "org-a", "settings": {"dialogueMemory": policy}}]
    db.tables["organization_members"] = [{"org_id": "org-a", "user_id": "user-a"}]
    row = {"id": "m1", "org_id": "org-a", "agent_id": "agent-a", "created_by": "user-a",
           "is_current": True, "is_active": True, "source_connector_id": None,
           "content": "Current synthetic preference", "category": "episodic",
           "source_class": "user_direct", "created_at": ANCHOR.isoformat(), **case.get("row", {})}
    db.tables["agent_memories"] = [row]
    hits = [{"id": "m1", "content": "Stale search result must never win", "category": "episodic"}]
    settings = SimpleNamespace(dialogue_memory_governance_v1=True, cross_conversation_ledger_memory_enabled=False,
                               memory_source_lineage_enabled=False)
    kernel = CognitiveTurnKernel(settings)
    request = CognitiveTurnRequest(org_id="org-a", user_id="user-a", agent_id="agent-a",
                                   conversation_id="conversation-a", message="Recall synthetic preferences", client=db)
    searches = 0
    candidate_requests = []

    async def search(*_args, **_kwargs):
        nonlocal searches
        searches += 1
        mutation = case.get("mutation")
        if mutation == "remove_member":
            db.tables["organization_members"] = []
        elif mutation == "revoke_recall":
            policy["recallEnabled"] = False
        elif mutation == "delete_row":
            db.tables["agent_memories"] = []
        elif mutation == "correct":
            row["superseded_by"] = "m2"
            db.tables["agent_memories"].append({**row, "id": "m2", "superseded_by": None,
                                              "content": "Corrected synthetic preference"})
            hits.append({"id": "m2", "category": "episodic"})
        elif mutation == "restore":
            row["content"] = "Restored authorized synthetic preference"
        elif mutation == "metadata_error":
            def unavailable(query):
                if query.table == "agent_memories" and query.op == "select":
                    raise RuntimeError("synthetic metadata unavailable")
            db.hooks.append(unavailable)
        if candidate_backend is not None:
            return await candidate_backend.recall(request, deepcopy(db.tables["agent_memories"]))
        if retrieval == "mem0_contract_replay":
            # Import pure research contracts only; no vendor constructor/SDK.
            import importlib.util
            from pathlib import Path
            import sys
            path = Path(__file__).resolve().parents[3] / "scripts/memory_benchmark/contracts.py"
            spec = importlib.util.spec_from_file_location("memory_replay_contracts", path)
            contracts = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = contracts
            spec.loader.exec_module(contracts)
            contract = contracts.mem0_search_contract(
                contracts.Scope(request.org_id, request.user_id, request.agent_id),
                request.message, namespace_key=b"synthetic-replay-key-never-secret",
            )
            candidate_requests.append(contract)
            if case.get("replay_fault") == "timeout":
                raise TimeoutError("synthetic candidate timeout")
            response = case.get("replay_response", {"results": [
                {"id": "vendor-" + hit["id"], "memory": "VENDOR_TEXT_MUST_NOT_ENTER_PROMPT",
                 "metadata": {"org_id": "org-b", "source_class": "user_direct", "approved": True}}
                for hit in hits
            ]})
            ids = contracts.canonical_mem0_hit_ids(
                response, trusted_bindings={"vendor-m1": "m1", "vendor-m2": "m2"},
            )
            # Only host-owned canonical IDs cross; final rehydration owns content.
            return {"episodic_memories": [{"id": rid} for rid in ids], "graph_context": []}
        return {"episodic_memories": deepcopy(hits), "graph_context": []}

    # Only external service inputs are fixtures. In particular, no policy,
    # final recall gate, memory writer or confidence decision is mocked.
    with (
        patch("app.services.dialogue_memory_policy.datetime", Clock),
        patch("app.services.hybrid_memory_service.HybridMemoryService", return_value=SimpleNamespace(query_all_memory=search)),
        patch("app.services.agent_memory_service.search_agent_memories", return_value=[]),
        patch("app.services.agent_memory_service.search_department_memories", return_value=[]),
        patch("app.rag.department.resolve_department_id_for_agent", return_value=(None, None)),
        patch("app.services.workspace_memory_service.recall_workspace", return_value=[]),
        patch("app.rag.embedding.get_embedding", return_value=None) as embedding,
        patch.object(kernel, "_persist_trace", new_callable=AsyncMock),
    ):
        if case.get("operation") == "learn":
            candidate = {"id": "new-memory", "category": "episodic", "content": "New synthetic preference",
                         "source_class": "user_direct", **case.get("candidate", {})}
            context = await kernel.run_learn(request, CognitiveTurnContext(turn_id="synthetic-turn"),
                                             act_result={"confirmed": True, "typed_memories": [candidate]})
            written = [r for r in db.tables["agent_memories"] if r["id"] == "new-memory"]
            indexed = await candidate_backend.learn(request, written) if candidate_backend is not None else len(written)
            matched = (indexed == case["expected_writes"] and context.learn["ok"] and len(written) == case["expected_writes"]
                       and embedding.call_count == case["expected_embeddings"]
                       and (not case.get("expected_class") or bool(written) and written[0]["source_class"] == case["expected_class"]))
            return {"id": case["id"], "passed": bool(matched), "writes": len(written), "embedding_calls": embedding.call_count}
        pack = await kernel._recall(request, db)
    items = [r for key in ("working", "episodic", "preference", "decision", "outcome", "relationship", "procedural") for r in pack[key]]
    ids = sorted(r["id"] for r in items)
    degraded = bool(pack["recall_stats"]["errors"])
    matched = (ids == case["expected_ids"] and searches == case.get("expected_searches", 1)
               and degraded == case.get("expected_degraded", False)
               and (retrieval != "mem0_contract_replay" or (len(candidate_requests) == searches
                    and "VENDOR_TEXT_MUST_NOT_ENTER_PROMPT" not in pack["prompt_section"]))
               and ("expected_errors" not in case or pack["recall_stats"]["errors"] == case["expected_errors"])
               and (not case.get("expected_text") or case["expected_text"] in pack["prompt_section"]))
    return {"id": case["id"], "passed": bool(matched), "recalled": len(ids), "search_calls": searches,
            "degraded": degraded, "failed_sources": list(pack["recall_stats"]["errors"]),
            "candidate_requests": len(candidate_requests)}
