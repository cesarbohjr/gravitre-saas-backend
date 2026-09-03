"""CognitiveTurnKernel — mandatory pre-ACT thinking sequence (Phase 1+)."""
from __future__ import annotations

import asyncio
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

# The five independent stores RECALL draws from. Named so a per-turn signal can
# say which one produced rows -- "memory recalled 3 things" is not actionable if
# nobody can tell whether they came from workspace recall or the ledger.
MEMORY_SOURCES = (
    "hybrid",
    "agent",
    "department",
    "ledger",
    "workspace",
)

# Reserved key on the memory pack carrying the recall signal. Every reader of
# the pack addresses specific keys (`_MEMORY_KEYS`, `prompt_section`) rather
# than iterating it, so an extra key is inert -- checked, not assumed.
RECALL_STATS_KEY = "recall_stats"

AUDIT_ACTION_MEMORY_RECALL = "memory.recalled"

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
    # full = every stage; conversational = spoken/simple — keep RECALL+GOVERN,
    # skip heavy Knowledge Fabric merge (not a second brain; write turns stay full).
    reasoning_depth: str = "full"


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
            recall_signal = memory_recall_signal(ctx)
            ctx.stages.append(
                StageRecord(
                    stage="RECALL",
                    ok=True,
                    ms=_elapsed_ms(t0),
                    # `keys` alone described the pack's shape, which is a
                    # constant, so the stage said nothing about what happened.
                    meta={"keys": list(_MEMORY_KEYS), "recall": recall_signal},
                )
            )
            await asyncio.to_thread(
                _emit_memory_recall_audit,
                client=client,
                request=request,
                signal=recall_signal,
                turn_id=turn_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("cognitive_recall_failed error=%s", exc)
            ctx.memory_pack = _empty_memory_pack()
            ctx.stages.append(
                StageRecord(stage="RECALL", ok=False, ms=_elapsed_ms(t0), meta={"error": str(exc)[:200]})
            )

        # 3 KNOWLEDGE — full fabric merge for consequential/full turns only.
        # Conversational spoken depth keeps RECALL + GOVERN; skips heavy retrieval.
        conversational = (request.reasoning_depth or "full").strip().lower() == "conversational"
        t0 = time.perf_counter()
        try:
            if conversational:
                ctx.knowledge_pack = {
                    "fabric_chunks": [],
                    "entity_section": "",
                    "catalog_hints": [],
                    "prompt_section": "",
                    "skipped": "conversational_depth",
                }
                ctx.stages.append(
                    StageRecord(
                        stage="KNOWLEDGE",
                        ok=True,
                        ms=_elapsed_ms(t0),
                        meta={"skipped": "conversational_depth", "fabric_count": 0},
                    )
                )
            else:
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

        # Outcome bias for PLAN (best-effort) — skip on conversational spoken depth.
        bias: dict[str, Any] = {"bias_notes": [], "weight_delta": 0.0}
        if not conversational:
            try:
                from app.services.cognitive_outcome_loop import bias_from_outcomes

                if client is not None:
                    bias = bias_from_outcomes(client, request.org_id, request.message or "", self.settings)
            except Exception as exc:  # noqa: BLE001
                logger.debug("cognitive_outcome_bias_skipped error=%s", exc)

        # Org metrics SoT — resolve mentioned KPI keys into knowledge/plan context
        metric_hits: list[dict[str, Any]] = []
        if not conversational:
            try:
                metric_hits = _resolve_mentioned_metrics(client, request.org_id, request.message or "")
                if metric_hits and isinstance(ctx.knowledge_pack, dict):
                    ctx.knowledge_pack = dict(ctx.knowledge_pack)
                    ctx.knowledge_pack["org_metrics"] = metric_hits
                    section = str(ctx.knowledge_pack.get("prompt_section") or "")
                    metric_lines = [
                        f"- {m.get('metric_key')}: {m.get('label')} "
                        f"(formula={m.get('formula') or 'n/a'}; source={m.get('resolved_from')})"
                        for m in metric_hits[:6]
                    ]
                    metric_block = (
                        "<org_metric_definitions>\n"
                        + "\n".join(metric_lines)
                        + "\nUse these org-scoped definitions when discussing KPIs. "
                        "Do not invent MQL/CAC/ARR formulas when a definition exists.\n"
                        "</org_metric_definitions>"
                    )
                    ctx.knowledge_pack["prompt_section"] = (
                        f"{section}\n\n{metric_block}".strip() if section else metric_block
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("cognitive_metrics_resolve_skipped error=%s", exc)

        # 4 PLAN
        t0 = time.perf_counter()
        try:
            from app.services.cognitive_planner import CognitivePlanner

            connected_integrations: list[str] = []
            department: str | None = None
            if client is not None:
                try:
                    from app.services.tool_registry import get_tool_registry

                    reg = get_tool_registry()
                    connected_integrations = reg.list_connected_integrations(
                        client,
                        request.org_id,
                        environment_name=request.environment_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("cognitive_plan_connected_integrations_skipped error=%s", exc)
                agent_row = request.agent if isinstance(request.agent, dict) else {}
                dept_name = str(agent_row.get("department") or "").strip().lower()
                if dept_name:
                    department = dept_name

            plan = CognitivePlanner().plan(
                request.message or "",
                request.task_state,
                ctx.memory_pack,
                ctx.knowledge_pack,
                connected_integrations=connected_integrations or None,
                department=department,
            )
            if bias.get("bias_notes"):
                plan = dict(plan)
                plan["outcome_bias"] = bias
            if metric_hits:
                plan = dict(plan)
                plan["org_metrics"] = metric_hits
            # Honest what-if (item 16) — product path into existing heuristic simulator
            if not conversational and _looks_like_what_if(request.message or ""):
                plan = dict(plan)
                try:
                    from app.services.cognitive_simulation_service import simulate_business_scenario

                    sim = await simulate_business_scenario(
                        org_id=request.org_id,
                        scenario=request.message or "",
                    )
                    plan["what_if"] = sim
                    steps = list(plan.get("steps") or [])
                    steps.append(
                        {
                            "step_id": "what_if_simulation",
                            "title": "Heuristic what-if projection",
                            "description": str((sim or {}).get("summary") or "")[:240],
                            "status": "pending",
                            "honesty": "heuristic_not_forecast",
                        }
                    )
                    plan["steps"] = steps
                except Exception as sim_exc:  # noqa: BLE001
                    logger.debug("cognitive_what_if_plan_skipped error=%s", sim_exc)
            ctx.plan = plan
            ctx.stages.append(
                StageRecord(
                    stage="PLAN",
                    ok=True,
                    ms=_elapsed_ms(t0),
                    meta={
                        "source": plan.get("source"),
                        "steps": len(plan.get("steps") or []),
                        "org_metrics": len(metric_hits),
                        "what_if": bool(plan.get("what_if")),
                        "reasoning_depth": request.reasoning_depth or "full",
                    },
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
                    meta={
                        "skipped": bool(ctx.verify.get("skipped")),
                        "mandatory": bool(ctx.verify.get("mandatory")),
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_verify_failed error=%s", exc)
            # Fail closed when the turn looks like a consequential write.
            write_like = _request_is_consequential_write(request)
            ctx.verify = {
                "passed": not write_like,
                "skipped": True,
                "error": str(exc)[:200],
                "mandatory": write_like,
            }
            ctx.stages.append(
                StageRecord(
                    stage="VERIFY",
                    ok=not write_like,
                    ms=_elapsed_ms(t0),
                    meta={"error": str(exc)[:200], "mandatory": write_like},
                )
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
                        "denied_fields": ctx.govern.get("denied_fields") or [],
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
        """LEARN stage after ACT — record outcomes + promote typed memories."""
        t0 = time.perf_counter()
        learn: dict[str, Any] = {"ok": True, "outcome_ids": [], "promoted_memory_ids": []}
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
            # Persist typed memories from confirmed turns (workspace-scoped).
            if request.org_id and request.client is not None:
                from app.services.workspace_memory_service import (
                    extract_typed_memories_from_act,
                    promote_turn_memories,
                )

                confirmed = bool(
                    (isinstance(act_result, dict) and act_result.get("confirmed"))
                    or (isinstance(act_result, dict) and act_result.get("promote_memories"))
                    or outcome_event
                )
                typed = extract_typed_memories_from_act(
                    act_result if confirmed else None,
                    outcome_event=outcome_event if confirmed else None,
                    message=request.message if (confirmed and outcome_event) else None,
                )
                if typed:
                    written = promote_turn_memories(
                        request.client,
                        org_id=request.org_id,
                        memories=typed,
                        agent_id=request.agent_id,
                        conversation_id=request.conversation_id,
                        user_id=request.user_id,
                        settings=self.settings,
                    )
                    learn["promoted_memory_ids"] = [
                        str(r.get("id")) for r in written if isinstance(r, dict) and r.get("id")
                    ]
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_learn_failed error=%s", exc)
            learn = {
                "ok": False,
                "error": str(exc)[:200],
                "outcome_ids": [],
                "promoted_memory_ids": [],
            }

        context.learn = learn
        context.stages.append(
            StageRecord(stage="LEARN", ok=bool(learn.get("ok")), ms=_elapsed_ms(t0), meta=learn)
        )
        await self._persist_trace(request, context)
        return context

    async def _recall(self, request: CognitiveTurnRequest, client: Any) -> dict[str, Any]:
        pack = _empty_memory_pack()
        stats = pack[RECALL_STATS_KEY]
        org_id = request.org_id
        if not org_id:
            # ran stays False: this is "did not execute", not "found nothing".
            return pack

        # Hybrid memory (org-scoped)
        got = 0
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
                    got += 1
            for row in bundle.get("graph_context") or []:
                if isinstance(row, dict):
                    pack["relationship"].append(row)
                    got += 1
            _note_recall(stats, "hybrid", count=got)
        except Exception as exc:  # noqa: BLE001
            # WARNING, not debug. All five of these stores logged at debug, which
            # is off in production, so a store that failed on every turn was
            # invisible and looked exactly like a store that found nothing.
            logger.warning("cognitive_hybrid_memory_failed error=%s", exc)
            _note_recall(stats, "hybrid", count=got, error=exc)

        # Agent memory search (org-scoped)
        if client is not None and request.agent_id:
            got = 0
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
                    got += 1
                _note_recall(stats, "agent", count=got)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cognitive_agent_memory_search_failed error=%s", exc)
                _note_recall(stats, "agent", count=got, error=exc)

            # Shared department memory: agents in the same department RECALL dept-scoped rows.
            got = 0
            try:
                from app.rag.department import resolve_department_id_for_agent
                from app.services.agent_memory_service import search_department_memories

                dept_id, _ = resolve_department_id_for_agent(client, org_id, request.agent_id)
                if dept_id:
                    dept_memories = search_department_memories(
                        self.settings,
                        client,
                        org_id,
                        dept_id,
                        query=request.message or "",
                        top_k=8,
                    )
                    seen_ids = {
                        str(r.get("id"))
                        for key in _MEMORY_KEYS
                        for r in (pack.get(key) or [])
                        if isinstance(r, dict) and r.get("id")
                    }
                    for row in dept_memories or []:
                        if not isinstance(row, dict):
                            continue
                        row_org = str(row.get("org_id") or org_id)
                        if row_org != org_id:
                            continue
                        mid = str(row.get("id") or "")
                        if mid and mid in seen_ids:
                            continue
                        if mid:
                            seen_ids.add(mid)
                        bucket = _CATEGORY_MAP.get(str(row.get("category") or "fact").lower(), "episodic")
                        pack[bucket].append({**row, "source": "department_shared_memory", "org_id": org_id})
                        got += 1
                _note_recall(stats, "department", count=got)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cognitive_department_memory_failed error=%s", exc)
                _note_recall(stats, "department", count=got, error=exc)

        # Org-scoped cross-conversation promotions (ledger/entity resolutions).
        # Never fuzzy person-name Option C — explicit promotions + typed memories only.
        if client is not None:
            got = 0
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
                            got += 1
                    _note_recall(stats, "ledger", count=got)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cognitive_cross_conversation_recall_failed error=%s", exc)
                _note_recall(stats, "ledger", count=got, error=exc)

            # Workspace recall: category + hybrid content match (org only; no Option C).
            got = 0
            try:
                from app.services.workspace_memory_service import (
                    TYPED_CATEGORIES,
                    recall_workspace,
                )

                # Prefer cognitive taxonomy categories when the query hints at them;
                # otherwise pull recent typed + legacy rows via hybrid scoring.
                hinted = [
                    c
                    for c in TYPED_CATEGORIES
                    if c in (request.message or "").lower()
                ]
                recalled = recall_workspace(
                    client,
                    org_id=org_id,
                    query=request.message or "",
                    categories=hinted or None,
                    top_k=12,
                    agent_id=request.agent_id,
                    settings=self.settings,
                )
                for row in recalled:
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("org_id") or "") != org_id:
                        continue
                    bucket = _CATEGORY_MAP.get(
                        str(row.get("category") or "fact").lower(), "episodic"
                    )
                    pack[bucket].append({**row, "source": row.get("source") or "workspace_memory_recall"})
                    got += 1
                _note_recall(stats, "workspace", count=got)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cognitive_workspace_memory_recall_failed error=%s", exc)
                _note_recall(stats, "workspace", count=got, error=exc)

        pack["prompt_section"] = _memory_prompt_section(pack)
        return pack

    async def _verify(
        self,
        request: CognitiveTurnRequest,
        ctx: CognitiveTurnContext,
    ) -> dict[str, Any]:
        # Pre-ACT verify is advisory/noop when there is no draft answer yet —
        # except consequential writes, which mark mandatory critic pending for post-ACT.
        draft = ""
        if isinstance(request.parameters, dict):
            draft = str(request.parameters.get("draft_answer") or request.parameters.get("answer") or "")
        consequential = _request_is_consequential_write(request)
        if not draft.strip():
            return {
                "passed": True,
                "issues": [],
                "skipped": "pre_act_no_draft",
                "critic": "noop",
                "mandatory": consequential,
                "mandatory_pending_post_act": consequential,
            }
        try:
            from app.services.verification_critic_service import get_verification_critic_service

            critic = get_verification_critic_service(self.settings)
            classification = {
                "requires_action": request.intent in {"write_confirm", "job", "enrich", "extension_action"},
                "intent": request.intent,
                "is_write": consequential,
                "risk_level": (request.parameters or {}).get("risk_level"),
                "invoke_action": (request.parameters or {}).get("invoke_action")
                or (request.parameters or {}).get("action"),
            }
            result = await critic.verify_before_delivery(
                query=request.message or "",
                answer=draft,
                classification=classification,
                org_id=request.org_id,
                rag_sources=list(ctx.knowledge_pack.get("fabric_chunks") or [])[:4],
                mandatory=consequential,
            )
            return result if isinstance(result, dict) else {"passed": True, "raw": result}
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_verify_best_effort_skipped error=%s", exc)
            if consequential:
                return {
                    "passed": False,
                    "skipped": True,
                    "error": str(exc)[:200],
                    "mandatory": True,
                    "issues": ["mandatory_critic_error"],
                }
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
        denied: list[str] = []
        redacted_preview: Any = None
        try:
            from app.services.cognitive_field_acl import assert_field_allowed, redact_payload

            role = str(params.get("role") or params.get("seat_role") or "member")
            resource = str(params.get("resource") or params.get("integration") or "conversation")
            fields = params.get("fields") or params.get("field_keys") or []
            if not isinstance(fields, list) or not fields:
                fields = _derive_field_keys(params)
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
                    denied = [c["field"] for c in field_checks if not c["allowed"]]
                    # Apply redact helper so GOVERN returns a safe preview of args.
                    args_preview = params.get("args") or params.get("parameters") or params.get("payload")
                    if isinstance(args_preview, dict):
                        redacted_preview = redact_payload(args_preview, denied)
                    try:
                        from app.workflows.audit import write_audit_event

                        if request.client is not None and request.user_id:
                            write_audit_event(
                                request.client,
                                org_id=request.org_id,
                                actor_id=str(request.user_id),
                                action="cognitive.govern.field_acl_deny",
                                resource_type="field_permission",
                                resource_id=request.org_id,
                                metadata={
                                    "role": role,
                                    "resource": resource,
                                    "deniedFields": denied,
                                    "surface": request.surface,
                                    "entryPoint": request.entry_point,
                                },
                            )
                    except Exception as audit_exc:  # noqa: BLE001
                        logger.debug("cognitive_field_acl_audit_skipped error=%s", audit_exc)
                    return {
                        "ok": False,
                        "requires_approval": True,
                        "blocked": "field_acl_deny",
                        "field_checks": field_checks,
                        "denied_fields": denied,
                        "redacted_args": redacted_preview,
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
                    "denied_fields": denied,
                }
            except Exception as exc:  # noqa: BLE001
                logger.debug("cognitive_govern_authority_skipped error=%s", exc)
                return {
                    "ok": True,
                    "requires_approval": True,
                    "actions": action_hints,
                    "error": str(exc)[:200],
                    "field_checks": field_checks,
                    "denied_fields": denied,
                }

        return {
            "ok": True,
            "requires_approval": False,
            "field_checks": field_checks,
            "denied_fields": denied,
        }

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
                "org_metrics": len((ctx.knowledge_pack or {}).get("org_metrics") or []),
            }
            confidence_summary = _confidence_summary_from_ctx(ctx, request)
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
                "confidence_summary": confidence_summary,
            }
            client.table("cognitive_turn_traces").insert(payload).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_turn_trace_persist_skipped error=%s", exc)


def to_prompt_sections(ctx: CognitiveTurnContext) -> dict[str, str]:
    """Build memory / knowledge / Mode A outcome-bias sections for prompt assembly."""
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
    outcome_bias_section = _outcome_bias_prompt_section(
        (ctx.plan or {}).get("outcome_bias") if isinstance(ctx.plan, dict) else None
    )
    what_if_section = _what_if_prompt_section(
        (ctx.plan or {}).get("what_if") if isinstance(ctx.plan, dict) else None
    )
    return {
        "memory_section": memory_section,
        "knowledge_section": knowledge_section,
        "outcome_bias_section": outcome_bias_section,
        "what_if_section": what_if_section,
    }


def _outcome_bias_prompt_section(bias: Any) -> str:
    """Mode A advisory bias — steers recommendations; never auto-mutates org policy."""
    if not isinstance(bias, dict):
        return ""
    notes = bias.get("bias_notes") or []
    if not isinstance(notes, list):
        notes = []
    notes = [str(n).strip() for n in notes if str(n).strip()]
    try:
        weight = float(bias.get("weight_delta") or 0.0)
    except (TypeError, ValueError):
        weight = 0.0
    if not notes and weight == 0.0:
        return ""
    lines = [
        "<outcome_bias mode=\"A\" advisory_only=\"true\">",
        "Prior recommendation outcomes (Mode A — human-approved learning only).",
        "Use these as advisory bias when recommending next steps.",
        "Do NOT invent policy changes, prices, or entitlements.",
        "After negative/rejected outcomes, prefer safer alternatives and say what failed before.",
        f"weight_delta={weight}",
    ]
    for note in notes[:8]:
        lines.append(f"- {note[:300]}")
    lines.append("</outcome_bias>")
    return "\n".join(lines)


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


def _empty_recall_stats() -> dict[str, Any]:
    """Zeroed per-source recall stats.

    ``attempted`` is the field that matters. Without it, a turn where every store
    was skipped is byte-identical to a turn where all five ran and found nothing,
    and those mean opposite things: the first says the instrument is blind, the
    second says memory is genuinely empty. The memory census read
    ``no_memory_signal`` on 1581 of 1581 turns and first reported it as "0 turns
    recalled memory" -- the same conflation, one layer up.
    """
    return {
        "ran": False,
        "sources": {
            name: {"attempted": False, "count": 0, "error": None} for name in MEMORY_SOURCES
        },
        "total": 0,
        "errors": [],
    }


def _note_recall(
    stats: dict[str, Any],
    source: str,
    *,
    count: int = 0,
    error: BaseException | None = None,
) -> None:
    """Record one store's outcome. Never raises -- instrumentation must not break RECALL."""
    try:
        entry = stats["sources"][source]
        entry["attempted"] = True
        entry["count"] = int(count)
        if error is not None:
            entry["error"] = type(error).__name__
            if source not in stats["errors"]:
                stats["errors"].append(source)
        stats["total"] = sum(int(s["count"]) for s in stats["sources"].values())
        stats["ran"] = True
    except Exception:  # noqa: BLE001
        pass


def _empty_memory_pack() -> dict[str, Any]:
    pack: dict[str, Any] = {k: [] for k in _MEMORY_KEYS}
    pack["prompt_section"] = ""
    pack[RECALL_STATS_KEY] = _empty_recall_stats()
    return pack


def memory_recall_signal(ctx: CognitiveTurnContext) -> dict[str, Any]:
    """The per-turn memory recall signal, in audit-payload shape.

    A named accessor rather than callers reaching into ``memory_pack`` by string
    key, so the pack's internal shape stays private and there is one place to
    change if it moves.

    Distinguishes three states that were previously one:

    * ``ran=False`` -- RECALL did not execute (kernel disabled, or no org).
      Sufficiency is UNKNOWN.
    * ``ran=True, total=0`` -- every attempted store genuinely returned nothing.
    * ``degraded=True`` -- at least one store raised. The count is a floor, not a
      measurement, and the event says so rather than letting a partial recall
      look complete. Lesson 5: a fail-open must announce itself.
    """
    pack = ctx.memory_pack if isinstance(ctx.memory_pack, dict) else {}
    stats = pack.get(RECALL_STATS_KEY)
    if not isinstance(stats, dict):
        stats = _empty_recall_stats()
    sources = stats.get("sources") or {}
    errors = list(stats.get("errors") or [])
    return {
        "ran": bool(stats.get("ran")),
        "total": int(stats.get("total") or 0),
        "bySource": {
            name: int((sources.get(name) or {}).get("count") or 0) for name in MEMORY_SOURCES
        },
        "attempted": [
            name for name in MEMORY_SOURCES if (sources.get(name) or {}).get("attempted")
        ],
        # Named `degraded` and not `ok`: the absence of a problem should not be
        # the thing a query has to infer.
        "degraded": bool(errors),
        "failedSources": errors,
    }


def _emit_memory_recall_audit(
    *,
    client: Any,
    request: CognitiveTurnRequest,
    signal: dict[str, Any],
    turn_id: str,
) -> None:
    """Give memory recall a queryable audit action when it actually contributed.

    **Why only when it contributed.** RECALL runs on essentially every kernel
    turn, so an unconditional row would add a write to the conversational fast
    path -- the one path that must not pay for this machinery -- and at current
    volume would record "0" a few thousand times. The sufficiency audit declined
    the same trade for the same reason.

    That is only safe because the zero case is still recorded, just for free:
    ``unifiedTurnKnowledge.memoryRecall`` rides the existing
    ``unified_turn.*`` event on every turn and carries ``ran`` and ``total``. So
    the two signals together separate the three states the census could not:

    * no ``memory.recalled`` row **and** ``memoryRecall.ran == true`` -> ran,
      found nothing. Real zero.
    * no ``memory.recalled`` row **and** ``memoryRecall`` absent -> never ran, or
      the signal is broken. Unknown, and loudly so.
    * a ``memory.recalled`` row -> memory reached the prompt, with per-source
      counts saying which store produced it.

    A ``degraded`` recall is emitted even at zero rows, because "every store
    failed" is exactly the finding that must not be filed as "found nothing".

    Never raises: an audit gap must not break a turn.
    """
    if client is None:
        return
    if not (signal.get("total") or signal.get("degraded")):
        return

    org_id = request.org_id
    actor_id = request.user_id
    conversation_id = request.conversation_id

    try:
        from app.core.uuid_utils import is_uuid  # type: ignore
    except Exception:  # noqa: BLE001

        def is_uuid(value: Any) -> bool:  # type: ignore[misc]
            import uuid as _uuid

            try:
                _uuid.UUID(str(value))
                return True
            except (ValueError, AttributeError, TypeError):
                return False

    if not (actor_id and is_uuid(actor_id)) or not (
        conversation_id and is_uuid(conversation_id)
    ):
        # Loudly. write_audit_event drops the insert when actor_id or
        # resource_id is not a uuid -- both columns are uuid NOT NULL -- and
        # three instruments in this program were written with actor_id=None,
        # read zero rows in production, and were nearly taken as proof that live
        # code was unreachable.
        logger.warning(
            "memory_recall_audit_skipped org_id=%s reason=non_uuid_actor_or_resource "
            "actor=%r conversation=%r total=%s degraded=%s",
            org_id,
            actor_id,
            conversation_id,
            signal.get("total"),
            signal.get("degraded"),
        )
        return

    try:
        from app.workflows.audit import write_audit_event

        write_audit_event(
            client,
            org_id,
            actor_id,
            AUDIT_ACTION_MEMORY_RECALL,
            "conversation",
            conversation_id,
            {
                **signal,
                # Without this the row cannot be attributed to a turn. The first
                # live proof read three rows in one window -- two probe turns and
                # one real `execute_task_streaming` turn -- and could not tell
                # whether that was three turns or one turn emitting three times.
                # An unattributable row makes "exactly one per turn" unverifiable,
                # which is a broken instrument, not a passing one. It also joins
                # to `unifiedTurnKnowledge.cognitiveTurnId` on the sibling event.
                "cognitiveTurnId": turn_id,
                "agentId": request.agent_id,
                "surface": request.surface,
                "entryPoint": request.entry_point,
                "reasoningDepth": request.reasoning_depth,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_recall_audit_failed org_id=%s error=%s", org_id, exc)


def _memory_prompt_section(pack: dict[str, Any]) -> str:
    """Format recalled memory. Admit low confidence rather than silently omitting."""
    lines: list[str] = ["<memory_pack>"]
    scores: list[float] = []
    any_items = False
    for key in _MEMORY_KEYS:
        items = pack.get(key) or []
        if not items:
            continue
        any_items = True
        lines.append(f"## {key}")
        for item in items[:5]:
            if isinstance(item, dict):
                raw_score = item.get("score")
                if raw_score is None:
                    raw_score = item.get("confidence")
                try:
                    if raw_score is not None:
                        scores.append(float(raw_score))
                except (TypeError, ValueError):
                    pass
                text = str(item.get("content") or item.get("memory_text") or item)[:300]
            else:
                text = str(item)[:300]
            if text:
                lines.append(f"- {text}")
    # Phase C: retrieval is lossy — say so when pack is empty or scores are weak.
    best = max(scores) if scores else None
    if not any_items:
        lines.append(
            "NOTE: No cross-conversation memories ranked into this turn. "
            "Related prior context may be missing — ask the user if recall seems incomplete."
        )
    elif best is not None and best < 0.35:
        lines.append(
            "NOTE: Related cross-conversation memory may be missing — "
            "retrieval confidence is low for this turn."
        )
    lines.append("</memory_pack>")
    return "\n".join(lines) if len(lines) > 2 else ""


def _elapsed_ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000.0, 2)


def _looks_like_what_if(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    needles = (
        "what if",
        "what-if",
        "whats if",
        "suppose we",
        "if we cut",
        "if we reduce",
        "scenario where",
        "counterfactual",
    )
    return any(n in text for n in needles)


def _request_is_consequential_write(request: CognitiveTurnRequest) -> bool:
    intent = (request.intent or "").lower()
    params = request.parameters if isinstance(request.parameters, dict) else {}
    if intent in {"write_confirm", "enrich", "extension_action"}:
        return True
    if bool(params.get("is_write")) or bool(params.get("is_destructive")):
        return True
    if bool(params.get("requires_write_approval")) or bool(params.get("requires_approval")):
        return True
    risk = str(params.get("risk_level") or "").lower()
    if risk in {"high", "critical"}:
        return True
    for key in ("action", "invoke_action", "action_key", "tool"):
        val = str(params.get(key) or "").lower()
        if val and any(tok in val for tok in (".create", ".update", ".delete", ".upsert", ".write")):
            return True
    return False


def _derive_field_keys(params: dict[str, Any]) -> list[str]:
    """Best-effort field keys from planned tool args for GOVERN ACL checks."""
    keys: list[str] = []
    seen: set[str] = set()

    def _add(name: Any) -> None:
        text = str(name or "").strip()
        if not text or text in seen or text.startswith("_"):
            return
        if text in {"args", "parameters", "payload", "fields", "field_keys"}:
            return
        seen.add(text)
        keys.append(text)

    for container_key in ("args", "parameters", "payload", "properties", "fields_map"):
        container = params.get(container_key)
        if isinstance(container, dict):
            for k in container.keys():
                _add(k)
        elif isinstance(container, list):
            for item in container:
                if isinstance(item, str):
                    _add(item)
                elif isinstance(item, dict) and item.get("name"):
                    _add(item.get("name"))
    explicit = params.get("field_keys") or params.get("fields")
    if isinstance(explicit, list):
        for item in explicit:
            _add(item)
    return keys[:40]


def _resolve_mentioned_metrics(client: Any, org_id: str, message: str) -> list[dict[str, Any]]:
    if not client or not org_id or not (message or "").strip():
        return []
    import re

    from app.services.cognitive_metrics import (
        list_metric_definitions,
        list_platform_defaults,
        resolve_metric,
    )

    defs = list_metric_definitions(client, org_id, limit=100)
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for row in defs:
        if not isinstance(row, dict):
            continue
        key = str(row.get("metric_key") or "").strip().lower()
        if key and key not in seen:
            candidates.append(row)
            seen.add(key)
    for row in list_platform_defaults():
        key = str(row.get("metric_key") or "").strip().lower()
        if key and key not in seen:
            candidates.append(row)
            seen.add(key)
    if not candidates:
        return []
    text = message.lower()
    hits: list[dict[str, Any]] = []
    for row in candidates:
        key = str(row.get("metric_key") or "").strip()
        label = str(row.get("label") or "").strip()
        if not key:
            continue
        token_hit = key.lower() in text or (label and label.lower() in text)
        # Also match bare tokens like MQL / CAC / ARR when they appear as words.
        if not token_hit and len(key) <= 8:
            if re.search(rf"\b{re.escape(key.lower())}\b", text):
                token_hit = True
        if token_hit:
            hits.append(resolve_metric(client, org_id, key, fallback_label=label or key))
    return hits[:8]


def _confidence_summary_from_ctx(
    ctx: CognitiveTurnContext,
    request: CognitiveTurnRequest,
) -> dict[str, Any]:
    """Build a compact confidence join for admin Cognitive turns console."""
    from app.services.confidence_honesty import (
        CONFIDENCE_SOURCE_HEURISTIC,
        label_confidence,
    )

    params = request.parameters if isinstance(request.parameters, dict) else {}
    raw = None
    source = CONFIDENCE_SOURCE_HEURISTIC
    is_estimate = True
    for candidate in (
        params.get("confidence"),
        (ctx.verify or {}).get("confidence"),
        (ctx.plan or {}).get("confidence") if isinstance(ctx.plan, dict) else None,
    ):
        if isinstance(candidate, dict):
            raw = candidate.get("confidence")
            if raw is None:
                raw = candidate.get("score")
            source = (
                candidate.get("confidence_source")
                or candidate.get("confidenceSource")
                or source
            )
            if candidate.get("confidence_is_estimate") is not None:
                is_estimate = bool(candidate.get("confidence_is_estimate"))
            elif candidate.get("confidenceIsEstimate") is not None:
                is_estimate = bool(candidate.get("confidenceIsEstimate"))
            break
        if isinstance(candidate, (int, float)):
            raw = float(candidate)
            break
    try:
        score = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        score = None
    labeled = label_confidence(score, source=str(source), is_estimate=bool(is_estimate))
    labeled["verify_passed"] = bool((ctx.verify or {}).get("passed", True))
    labeled["verify_mandatory"] = bool((ctx.verify or {}).get("mandatory"))
    labeled["total_stage_ms"] = round(
        sum(float(getattr(s, "ms", 0) or 0) for s in (ctx.stages or [])), 2
    )
    return labeled


def _what_if_prompt_section(sim: Any) -> str:
    if not isinstance(sim, dict) or not sim.get("ok"):
        return ""
    lines = [
        "<what_if honesty=\"heuristic_not_forecast\">",
        str(sim.get("disclaimer") or "Heuristic scenario only — not a factual forecast."),
        f"summary: {str(sim.get('summary') or '')[:400]}",
    ]
    for proj in (sim.get("projections") or [])[:6]:
        if isinstance(proj, dict):
            lines.append(
                f"- {proj.get('dimension')}: {proj.get('direction')} "
                f"({str(proj.get('note') or '')[:160]})"
            )
    lines.append("</what_if>")
    return "\n".join(lines)
