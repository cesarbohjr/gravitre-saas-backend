"""CognitiveTurnKernel — mandatory pre-ACT thinking sequence (Phase 1+)."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_MEMORY_KEYS = (
    "working",
    "episodic",
    "preference",
    "decision",
    "outcome",
    "relationship",
    "procedural",
)

# Legacy agent_memories categories → cognitive taxonomy buckets
_CATEGORY_MAP = {
    "fact": "episodic",
    "preference": "preference",
    "pattern": "procedural",
    "rule": "decision",
    "working": "working",
    "episodic": "episodic",
    "decision": "decision",
    "outcome": "outcome",
    "relationship": "relationship",
    "procedural": "procedural",
    "campaign_learning": "episodic",
    "risk_signal": "decision",
    "business_rule": "decision",
}


@dataclass
class CognitiveTurnRequest:
    org_id: str
    message: str
    user_id: str | None = None
    agent_id: str | None = None
    conversation_id: str | None = None
    surface: str = "ai_chat"
    entry_point: str = "unknown"
    environment_name: str = "production"
    spoken_mode: bool = False
    intent: str = "chat"
    parameters: dict[str, Any] = field(default_factory=dict)
    task_state: dict[str, Any] | None = None
    conversation_history: list[Any] | None = None
    client: Any | None = None
    agent: dict[str, Any] | None = None


@dataclass
class StageRecord:
    stage: str
    ok: bool
    ms: float
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveTurnContext:
    turn_id: str
    identity: dict[str, Any] = field(default_factory=dict)
    memory_pack: dict[str, Any] = field(default_factory=dict)
    knowledge_pack: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    verify: dict[str, Any] = field(default_factory=dict)
    govern: dict[str, Any] = field(default_factory=dict)
    act: dict[str, Any] = field(default_factory=dict)
    learn: dict[str, Any] = field(default_factory=dict)
    stages: list[StageRecord] = field(default_factory=list)
    skipped: bool = False


@dataclass
class CognitiveTurnResult:
    turn_id: str
    context: CognitiveTurnContext
    stream_or_result: Any = None
    fallthrough_reason: str | None = None


class CognitiveTurnKernel:
    """Run RETRIEVE → RECALL → KNOWLEDGE → PLAN → VERIFY → GOVERN (stop before ACT)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def run_pre_act(self, request: CognitiveTurnRequest) -> CognitiveTurnContext:
        turn_id = str(uuid4())
        if not getattr(self.settings, "cognitive_turn_kernel_enabled", True):
            ctx = CognitiveTurnContext(
                turn_id=turn_id,
                identity=_identity_from_request(request),
                stages=[StageRecord(stage="skipped", ok=True, ms=0.0, meta={"reason": "flag_disabled"})],
                skipped=True,
                memory_pack=_empty_memory_pack(),
                knowledge_pack={},
                plan={"steps": [], "summary": "", "source": "skipped"},
                verify={"passed": True, "skipped": True},
                govern={"ok": True, "requires_approval": False, "skipped": True},
            )
            await self._persist_trace(request, ctx)
            return ctx

        if not request.org_id:
            raise ValueError("CognitiveTurnRequest.org_id is required (cross-org isolation)")

        ctx = CognitiveTurnContext(turn_id=turn_id)
        client = request.client

        # 1 RETRIEVE
        t0 = time.perf_counter()
        ctx.identity = _identity_from_request(request)
        ctx.stages.append(
            StageRecord(
                stage="RETRIEVE",
                ok=True,
                ms=_elapsed_ms(t0),
                meta={"surface": request.surface, "entry_point": request.entry_point},
            )
        )

        # 2 RECALL
        t0 = time.perf_counter()
        try:
            ctx.memory_pack = await self._recall(request, client)
            ctx.stages.append(
                StageRecord(
                    stage="RECALL",
                    ok=True,
                    ms=_elapsed_ms(t0),
                    meta={"keys": list(_MEMORY_KEYS)},
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_recall_failed error=%s", exc)
            ctx.memory_pack = _empty_memory_pack()
            ctx.stages.append(
                StageRecord(stage="RECALL", ok=False, ms=_elapsed_ms(t0), meta={"error": str(exc)[:200]})
            )

        # 3 KNOWLEDGE
        t0 = time.perf_counter()
        try:
            from app.services.cognitive_knowledge_layer import merge as merge_knowledge

            ctx.knowledge_pack = await merge_knowledge(
                client=client,
                org_id=request.org_id,
                query=request.message or "",
                agent=request.agent or ({"id": request.agent_id} if request.agent_id else None),
                settings=self.settings,
                user_id=request.user_id,
            )
            ctx.stages.append(
                StageRecord(
                    stage="KNOWLEDGE",
                    ok=True,
                    ms=_elapsed_ms(t0),
                    meta={"fabric_count": len(ctx.knowledge_pack.get("fabric_chunks") or [])},
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_knowledge_failed error=%s", exc)
            ctx.knowledge_pack = {
                "fabric_chunks": [],
                "entity_section": "",
                "catalog_hints": [],
                "prompt_section": "",
            }
            ctx.stages.append(
                StageRecord(stage="KNOWLEDGE", ok=False, ms=_elapsed_ms(t0), meta={"error": str(exc)[:200]})
            )

        # Outcome bias for PLAN (best-effort)
        bias: dict[str, Any] = {"bias_notes": [], "weight_delta": 0.0}
        try:
            from app.services.cognitive_outcome_loop import bias_from_outcomes

            if client is not None:
                bias = bias_from_outcomes(client, request.org_id, request.message or "", self.settings)
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_outcome_bias_skipped error=%s", exc)

        # 4 PLAN
        t0 = time.perf_counter()
        try:
            from app.services.cognitive_planner import CognitivePlanner

            plan = CognitivePlanner().plan(
                request.message or "",
                request.task_state,
                ctx.memory_pack,
                ctx.knowledge_pack,
            )
            if bias.get("bias_notes"):
                plan = dict(plan)
                plan["outcome_bias"] = bias
            ctx.plan = plan
            ctx.stages.append(
                StageRecord(
                    stage="PLAN",
                    ok=True,
                    ms=_elapsed_ms(t0),
                    meta={"source": plan.get("source"), "steps": len(plan.get("steps") or [])},
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_plan_failed error=%s", exc)
            ctx.plan = {"steps": [], "summary": "", "source": "cognitive_planner", "error": str(exc)[:200]}
            ctx.stages.append(
                StageRecord(stage="PLAN", ok=False, ms=_elapsed_ms(t0), meta={"error": str(exc)[:200]})
            )

        # 5 VERIFY
        t0 = time.perf_counter()
        try:
            ctx.verify = await self._verify(request, ctx)
            ctx.stages.append(
                StageRecord(
                    stage="VERIFY",
                    ok=bool(ctx.verify.get("passed", True)),
                    ms=_elapsed_ms(t0),
                    meta={"skipped": bool(ctx.verify.get("skipped"))},
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_verify_failed error=%s", exc)
            ctx.verify = {"passed": True, "skipped": True, "error": str(exc)[:200]}
            ctx.stages.append(
                StageRecord(stage="VERIFY", ok=True, ms=_elapsed_ms(t0), meta={"error": str(exc)[:200]})
            )

        # 6 GOVERN
        t0 = time.perf_counter()
        try:
            ctx.govern = self._govern(request)
            ctx.stages.append(
                StageRecord(
                    stage="GOVERN",
                    ok=bool(ctx.govern.get("ok", True)),
                    ms=_elapsed_ms(t0),
                    meta={
                        "requires_approval": bool(ctx.govern.get("requires_approval")),
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_govern_failed error=%s", exc)
            ctx.govern = {"ok": True, "requires_approval": False, "error": str(exc)[:200]}
            ctx.stages.append(
                StageRecord(stage="GOVERN", ok=False, ms=_elapsed_ms(t0), meta={"error": str(exc)[:200]})
            )

        await self._persist_trace(request, ctx)
        return ctx

    async def run_learn(
        self,
        request: CognitiveTurnRequest,
        context: CognitiveTurnContext,
        *,
        act_result: dict[str, Any] | None = None,
        recommendation_id: str | None = None,
        outcome_event: str | None = None,
    ) -> CognitiveTurnContext:
        """LEARN stage after ACT — record outcome events (best-effort)."""
        t0 = time.perf_counter()
        learn: dict[str, Any] = {"ok": True, "outcome_ids": []}
        try:
            if recommendation_id and outcome_event and request.org_id:
                from app.services.cognitive_outcome_loop import record_closed_loop

                recorded = await record_closed_loop(
                    org_id=request.org_id,
                    recommendation_id=recommendation_id,
                    outcome_event=outcome_event,
                    settings=self.settings,
                )
                learn["record"] = recorded
                if recorded.get("ok"):
                    learn["outcome_ids"].append(recommendation_id)
            if isinstance(act_result, dict):
                learn["act_summary"] = {
                    k: act_result.get(k)
                    for k in ("status", "success", "action", "error")
                    if k in act_result
                }
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_learn_failed error=%s", exc)
            learn = {"ok": False, "error": str(exc)[:200], "outcome_ids": []}

        context.learn = learn
        context.stages.append(
            StageRecord(stage="LEARN", ok=bool(learn.get("ok")), ms=_elapsed_ms(t0), meta=learn)
        )
        await self._persist_trace(request, context)
        return context

    async def _recall(self, request: CognitiveTurnRequest, client: Any) -> dict[str, Any]:
        pack = _empty_memory_pack()
        org_id = request.org_id
        if not org_id:
            return pack

        # Hybrid memory (org-scoped)
        try:
            from app.services.hybrid_memory_service import HybridMemoryService

            hybrid = HybridMemoryService(self.settings)
            bundle = await hybrid.query_all_memory(
                org_id,
                request.agent_id,
                request.message or "",
                top_k=8,
            )
            for row in bundle.get("episodic_memories") or []:
                if isinstance(row, dict):
                    bucket = _CATEGORY_MAP.get(str(row.get("category") or "fact").lower(), "episodic")
                    pack[bucket].append(row)
            for row in bundle.get("graph_context") or []:
                if isinstance(row, dict):
                    pack["relationship"].append(row)
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_hybrid_memory_skipped error=%s", exc)

        # Agent memory search (org-scoped)
        if client is not None and request.agent_id:
            try:
                from app.services.agent_memory_service import search_agent_memories

                memories = search_agent_memories(
                    self.settings,
                    client,
                    org_id,
                    request.agent_id,
                    query=request.message or "",
                    top_k=8,
                )
                for row in memories or []:
                    if not isinstance(row, dict):
                        continue
                    # Hard isolation: never accept a row from a foreign org.
                    row_org = str(row.get("org_id") or org_id)
                    if row_org != org_id:
                        continue
                    bucket = _CATEGORY_MAP.get(str(row.get("category") or "fact").lower(), "episodic")
                    pack[bucket].append(row)
            except Exception as exc:  # noqa: BLE001
                logger.debug("cognitive_agent_memory_search_skipped error=%s", exc)

        # Org-scoped cross-conversation promotions (ledger/entity resolutions).
        # Never fuzzy person-name Option C — explicit promotions + typed memories only.
        if client is not None:
            try:
                from app.services.cross_conversation_ledger_memory import (
                    feature_enabled as ledger_mem_enabled,
                )
                from app.services.entity_resolution_store import lookup_resolutions
                from app.services.parameter_ledger import get_ledger

                if ledger_mem_enabled(self.settings):
                    ledger = get_ledger(request.task_state)
                    aliases = [
                        a
                        for a in [
                            ledger.get("to"),
                            ledger.get("email"),
                            ledger.get("channel"),
                            *(str(t) for t in (request.message or "").split() if "@" in t),
                        ]
                        if a
                    ]
                    if aliases:
                        hits = lookup_resolutions(client, org_id, aliases, limit=20)
                        for hit in hits or []:
                            pack["relationship"].append(
                                {
                                    "category": "relationship",
                                    "content": f"{hit.entity_type}:{hit.entity_id}",
                                    "alias": hit.alias_normalized,
                                    "source": "cross_conversation_entity_memory",
                                    "org_id": org_id,
                                }
                            )
            except Exception as exc:  # noqa: BLE001
                logger.debug("cognitive_cross_conversation_recall_skipped error=%s", exc)

            # Promoted memories from other conversations in the same org only.
            try:
                rows = (
                    client.table("agent_memories")
                    .select("id,org_id,agent_id,category,content,created_at")
                    .eq("org_id", org_id)
                    .order("created_at", desc=True)
                    .limit(12)
                    .execute()
                    .data
                    or []
                )
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("org_id") or "") != org_id:
                        continue
                    bucket = _CATEGORY_MAP.get(str(row.get("category") or "fact").lower(), "episodic")
                    pack[bucket].append({**row, "source": "org_cross_conversation_memory"})
            except Exception as exc:  # noqa: BLE001
                logger.debug("cognitive_org_memory_scan_skipped error=%s", exc)

        pack["prompt_section"] = _memory_prompt_section(pack)
        return pack

    async def _verify(
        self,
        request: CognitiveTurnRequest,
        ctx: CognitiveTurnContext,
    ) -> dict[str, Any]:
        # Pre-ACT verify is advisory/noop when there is no draft answer yet.
        draft = ""
        if isinstance(request.parameters, dict):
            draft = str(request.parameters.get("draft_answer") or request.parameters.get("answer") or "")
        if not draft.strip():
            return {
                "passed": True,
                "issues": [],
                "skipped": "pre_act_no_draft",
                "critic": "noop",
            }
        try:
            from app.services.verification_critic_service import get_verification_critic_service

            critic = get_verification_critic_service(self.settings)
            result = await critic.verify_before_delivery(
                query=request.message or "",
                answer=draft,
                classification={"requires_action": request.intent in {"write_confirm", "job"}},
                org_id=request.org_id,
                rag_sources=list(ctx.knowledge_pack.get("fabric_chunks") or [])[:4],
            )
            return result if isinstance(result, dict) else {"passed": True, "raw": result}
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_verify_best_effort_skipped error=%s", exc)
            return {"passed": True, "skipped": True, "error": str(exc)[:200]}

    def _govern(self, request: CognitiveTurnRequest) -> dict[str, Any]:
        intent = (request.intent or "").lower()
        write_intent = intent in {"write_confirm", "enrich", "extension_action"} or bool(
            (request.parameters or {}).get("is_write")
        )
        action_hints: list[str] = []
        params = request.parameters or {}
        for key in ("action", "invoke_action", "action_key", "tool"):
            val = params.get(key)
            if isinstance(val, str) and val.strip():
                action_hints.append(val.strip())
        hints = params.get("action_hints")
        if isinstance(hints, list):
            action_hints.extend(str(h) for h in hints if h)

        field_checks: list[dict[str, Any]] = []
        try:
            from app.services.cognitive_field_acl import assert_field_allowed

            role = str(params.get("role") or params.get("seat_role") or "member")
            resource = str(params.get("resource") or "conversation")
            fields = params.get("fields") or params.get("field_keys") or []
            if isinstance(fields, list) and request.client is not None:
                for fk in fields:
                    allowed = assert_field_allowed(
                        request.client,
                        request.org_id,
                        role,
                        resource,
                        str(fk),
                    )
                    field_checks.append({"field": str(fk), "allowed": bool(allowed)})
                if field_checks and not all(c["allowed"] for c in field_checks):
                    return {
                        "ok": False,
                        "requires_approval": True,
                        "blocked": "field_acl_deny",
                        "field_checks": field_checks,
                        "actions": action_hints,
                    }
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_govern_field_acl_skipped error=%s", exc)

        if write_intent and action_hints:
            try:
                from app.services.catalog_write_authority import invoke_action_requires_write_approval

                requires = any(invoke_action_requires_write_approval(a) for a in action_hints)
                return {
                    "ok": True,
                    "requires_approval": bool(requires),
                    "actions": action_hints,
                    "field_checks": field_checks,
                }
            except Exception as exc:  # noqa: BLE001
                logger.debug("cognitive_govern_authority_skipped error=%s", exc)
                return {
                    "ok": True,
                    "requires_approval": True,
                    "actions": action_hints,
                    "error": str(exc)[:200],
                    "field_checks": field_checks,
                }

        return {"ok": True, "requires_approval": False, "field_checks": field_checks}

    async def _persist_trace(self, request: CognitiveTurnRequest, ctx: CognitiveTurnContext) -> None:
        client = request.client
        if client is None or not request.org_id:
            return
        try:
            stages_payload = [
                asdict(s) if isinstance(s, StageRecord) else s for s in (ctx.stages or [])
            ]
            memory_summary = {
                k: len(ctx.memory_pack.get(k) or [])
                for k in _MEMORY_KEYS
                if isinstance(ctx.memory_pack, dict)
            }
            knowledge_summary = {
                "fabric_chunks": len((ctx.knowledge_pack or {}).get("fabric_chunks") or []),
                "has_entity": bool((ctx.knowledge_pack or {}).get("entity_section")),
            }
            payload = {
                "id": str(uuid4()),
                "org_id": request.org_id,
                "user_id": request.user_id,
                "conversation_id": request.conversation_id,
                "turn_id": ctx.turn_id,
                "surface": request.surface,
                "stages": stages_payload,
                "memory_summary": memory_summary,
                "knowledge_summary": knowledge_summary,
            }
            client.table("cognitive_turn_traces").insert(payload).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_turn_trace_persist_skipped error=%s", exc)


def to_prompt_sections(ctx: CognitiveTurnContext) -> dict[str, str]:
    """Build memory_section / knowledge_section strings for prompt assembly."""
    memory_section = ""
    knowledge_section = ""
    if isinstance(ctx.memory_pack, dict):
        memory_section = str(ctx.memory_pack.get("prompt_section") or "")
        if not memory_section:
            memory_section = _memory_prompt_section(ctx.memory_pack)
    if isinstance(ctx.knowledge_pack, dict):
        knowledge_section = str(ctx.knowledge_pack.get("prompt_section") or "")
        if not knowledge_section:
            entity = str(ctx.knowledge_pack.get("entity_section") or "")
            knowledge_section = entity
    return {
        "memory_section": memory_section,
        "knowledge_section": knowledge_section,
    }


def get_cognitive_turn_kernel(settings: Settings | None = None) -> CognitiveTurnKernel:
    return CognitiveTurnKernel(settings or get_settings())


def _identity_from_request(request: CognitiveTurnRequest) -> dict[str, Any]:
    return {
        "org_id": request.org_id,
        "user_id": request.user_id,
        "agent_id": request.agent_id,
        "conversation_id": request.conversation_id,
        "surface": request.surface,
        "entry_point": request.entry_point,
        "environment_name": request.environment_name,
        "spoken_mode": request.spoken_mode,
        "intent": request.intent,
    }


def _empty_memory_pack() -> dict[str, Any]:
    pack: dict[str, Any] = {k: [] for k in _MEMORY_KEYS}
    pack["prompt_section"] = ""
    return pack


def _memory_prompt_section(pack: dict[str, Any]) -> str:
    lines: list[str] = ["<memory_pack>"]
    for key in _MEMORY_KEYS:
        items = pack.get(key) or []
        if not items:
            continue
        lines.append(f"## {key}")
        for item in items[:5]:
            if isinstance(item, dict):
                text = str(item.get("content") or item.get("memory_text") or item)[:300]
            else:
                text = str(item)[:300]
            if text:
                lines.append(f"- {text}")
    lines.append("</memory_pack>")
    return "\n".join(lines) if len(lines) > 2 else ""


def _elapsed_ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000.0, 2)
