"""Single mandatory cognitive loop for every non-fast-path request.

Closes the standing finding that this program had brain-adjacent parts,
not one brain. This controller does not reinvent PERCEIVE / RETRIEVE /
PLAN / ACT / OBSERVE / LEARN — it owns the order and the evidence that
each existing subsystem actually ran.

Sequence (deterministic, not optional):

    PERCEIVE  → Intent Gateway (already the sole PEP)
    RETRIEVE  → CognitiveTurnKernel RETRIEVE + RECALL + KNOWLEDGE
    PLAN      → CognitiveTurnKernel PLAN (CognitivePlanner)
    ACT       → existing catalog / LIVE / orchestration (caller)
    OBSERVE   → F6 verified-completion coverage + scheduled read-back
    COMPOSE   → Response Composer (mandatory; after OBSERVE, before any UI text)
    LEARN     → GIBE / cognitive_outcome_loop via kernel.run_learn

The only legal skip is the Intent Gateway's own proven fast-path for
genuinely simple, high-confidence turns. Operator-task-shaped requests
never take that path and must show all six stages.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

LOOP_STAGES: tuple[str, ...] = (
    "PERCEIVE",
    "RETRIEVE",
    "PLAN",
    "ACT",
    "OBSERVE",
    "LEARN",
)

USER_STAGE_LABELS: dict[str, str] = {
    "PERCEIVE": "Classifying request",
    "RETRIEVE": "Loading memory and knowledge",
    "PLAN": "Planning next actions",
    "ACT": "Preparing actions",
    "OBSERVE": "Checking the result",
    "LEARN": "Learning from the outcome",
}

AUDIT_ACTION_LOOP_COMPLETED = "cognitive.loop.completed"
SKIP_GATEWAY_FAST_PATH = "intent_gateway_fast_path"
KERNEL_RETRIEVE_STAGES = frozenset({"RETRIEVE", "RECALL", "KNOWLEDGE"})


@dataclass
class LoopStageRecord:
    stage: str
    ok: bool
    ms: float = 0.0
    skipped: bool = False
    skip_reason: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


@dataclass
class CognitiveLoopTrace:
    loop_id: str
    message: str
    spoken_mode: bool
    operator_task: bool
    stages: list[LoopStageRecord] = field(default_factory=list)
    turn_id: str | None = None
    fast_path: bool = False
    gateway_candidate: str | None = None
    gateway_reason: str | None = None

    def record(
        self,
        stage: str,
        *,
        ok: bool = True,
        ms: float = 0.0,
        skipped: bool = False,
        skip_reason: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> LoopStageRecord:
        rec = LoopStageRecord(
            stage=stage,
            ok=ok,
            ms=round(float(ms or 0.0), 1),
            skipped=skipped,
            skip_reason=skip_reason,
            evidence=dict(evidence or {}),
        )
        self.stages = [s for s in self.stages if s.stage != stage]
        self.stages.append(rec)
        return rec

    def stage_map(self) -> dict[str, LoopStageRecord]:
        return {s.stage: s for s in self.stages}

    def has_full_loop(self) -> bool:
        if self.fast_path:
            return False
        present = {s.stage for s in self.stages if not s.skipped}
        return all(name in present for name in LOOP_STAGES)

    def progress_steps(self, *, connected_integrations: list[str] | None = None) -> list[str]:
        names = [str(c) for c in (connected_integrations or [])[:4] if str(c).strip()]
        act_label = ", ".join(n.capitalize() for n in names) if names else "connected systems"
        out: list[str] = []
        for name in LOOP_STAGES:
            rec = self.stage_map().get(name)
            label = USER_STAGE_LABELS[name]
            if name == "ACT":
                label = f"Preparing actions for {act_label}"
            if rec is None:
                out.append(label)
            elif rec.skipped:
                continue
            elif rec.ok:
                out.append(f"Completed: {label}")
            else:
                out.append(f"Running: {label}")
        return out

    def to_sse(self) -> dict[str, Any]:
        return {
            "cognitiveLoop": True,
            "loopId": self.loop_id,
            "operatorTask": self.operator_task,
            "fastPath": self.fast_path,
            "spokenMode": bool(self.spoken_mode),
            "turnId": self.turn_id,
            "stages": [s.to_dict() for s in self.stages],
            "fullLoop": self.has_full_loop(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "spoken_mode": self.spoken_mode,
            "operator_task": self.operator_task,
            "fast_path": self.fast_path,
            "turn_id": self.turn_id,
            "gateway_candidate": self.gateway_candidate,
            "gateway_reason": self.gateway_reason,
            "stages": [s.to_dict() for s in self.stages],
            "full_loop": self.has_full_loop(),
        }


def _elapsed_ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000.0, 1)


def _is_operator_task(message: str) -> bool:
    from app.services.operator_task_intent import is_operator_task_shaped

    return bool(is_operator_task_shaped(message or ""))


class CognitiveLoopController:
    """Owns PERCEIVE → RETRIEVE → PLAN → ACT → OBSERVE → LEARN for one turn."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def begin(self, *, message: str, spoken_mode: bool) -> CognitiveLoopTrace:
        return CognitiveLoopTrace(
            loop_id=str(uuid4()),
            message=message or "",
            spoken_mode=bool(spoken_mode),
            operator_task=_is_operator_task(message or ""),
        )

    def mark_perceive(
        self,
        trace: CognitiveLoopTrace,
        gateway: Any,
        *,
        ms: float = 0.0,
    ) -> CognitiveLoopTrace:
        action = str(getattr(gateway, "action", "") or "")
        trace.gateway_candidate = getattr(gateway, "candidate_id", None)
        trace.gateway_reason = str(getattr(gateway, "reason", "") or "")
        trace.fast_path = action == "shortcut"
        evidence = {
            "action": action,
            "reason": trace.gateway_reason,
            "candidate_id": trace.gateway_candidate,
            "confidence": getattr(gateway, "confidence", None),
        }
        if trace.fast_path:
            if trace.operator_task:
                # Proven gateway rule forbids this. Record the contradiction
                # instead of silently continuing a shortcut.
                trace.fast_path = False
                trace.record(
                    "PERCEIVE",
                    ok=False,
                    ms=ms,
                    evidence={**evidence, "rejected_shortcut": "operator_task_shaped"},
                )
                return trace
            trace.record("PERCEIVE", ok=True, ms=ms, evidence=evidence)
            for stage in LOOP_STAGES[1:]:
                trace.record(
                    stage,
                    ok=True,
                    skipped=True,
                    skip_reason=SKIP_GATEWAY_FAST_PATH,
                    evidence={"reason": SKIP_GATEWAY_FAST_PATH},
                )
            return trace
        trace.record("PERCEIVE", ok=True, ms=ms, evidence=evidence)
        return trace

    def reasoning_depth_for(self, *, message: str, spoken_mode: bool, current: str | None = None) -> str:
        """Operator-task-shaped turns always keep full retrieval/planning depth."""
        _ = spoken_mode
        if _is_operator_task(message):
            return "full"
        depth = (current or "full").strip().lower() or "full"
        return depth

    def attach_retrieve_and_plan(
        self,
        trace: CognitiveLoopTrace,
        cognitive_ctx: Any,
    ) -> CognitiveLoopTrace:
        if trace.fast_path:
            return trace
        stages = list(getattr(cognitive_ctx, "stages", None) or [])
        by_name: dict[str, Any] = {}
        for rec in stages:
            name = str(getattr(rec, "stage", "") or "")
            if name:
                by_name[name] = rec
        trace.turn_id = str(getattr(cognitive_ctx, "turn_id", "") or "") or trace.turn_id

        retrieve_ms = 0.0
        retrieve_ok = True
        retrieve_evidence: dict[str, Any] = {"kernel_stages": []}
        for name in ("RETRIEVE", "RECALL", "KNOWLEDGE"):
            rec = by_name.get(name)
            if rec is None:
                retrieve_ok = False
                retrieve_evidence["missing"] = retrieve_evidence.get("missing", []) + [name]
                continue
            retrieve_ms += float(getattr(rec, "ms", 0) or 0)
            retrieve_ok = retrieve_ok and bool(getattr(rec, "ok", True))
            meta = dict(getattr(rec, "meta", None) or {})
            retrieve_evidence["kernel_stages"].append(
                {"stage": name, "ok": bool(getattr(rec, "ok", True)), "ms": getattr(rec, "ms", 0), "meta": meta}
            )
            if meta.get("skipped"):
                retrieve_evidence["skipped_kernel"] = meta.get("skipped")
        knowledge = getattr(cognitive_ctx, "knowledge_pack", None) or {}
        if isinstance(knowledge, dict):
            retrieve_evidence["fabric_count"] = len(knowledge.get("fabric_chunks") or [])
            retrieve_evidence["signal_scoring"] = bool(knowledge.get("signal_scoring"))
            retrieve_evidence["sufficiency"] = knowledge.get("sufficiency")
            if knowledge.get("skipped"):
                retrieve_evidence["knowledge_skipped"] = knowledge.get("skipped")
                if trace.operator_task:
                    retrieve_ok = False
        trace.record("RETRIEVE", ok=retrieve_ok, ms=retrieve_ms, evidence=retrieve_evidence)

        plan_rec = by_name.get("PLAN")
        plan = getattr(cognitive_ctx, "plan", None) or {}
        plan_ok = True if plan_rec is None else bool(getattr(plan_rec, "ok", True))
        plan_evidence: dict[str, Any] = {
            "step_count": len((plan or {}).get("steps") or []) if isinstance(plan, dict) else 0,
            "source": (plan or {}).get("source") if isinstance(plan, dict) else None,
            "has_signal_priorities": bool(
                isinstance(plan, dict) and (plan.get("signal_scoring") or plan.get("signal_priorities"))
            ),
        }
        if isinstance(knowledge, dict) and knowledge.get("signal_scoring"):
            plan_evidence["signal_scoring"] = True
        trace.record(
            "PLAN",
            ok=plan_ok,
            ms=float(getattr(plan_rec, "ms", 0) or 0) if plan_rec is not None else 0.0,
            evidence=plan_evidence,
        )
        return trace

    async def observe_and_learn(
        self,
        trace: CognitiveLoopTrace,
        *,
        request: Any,
        cognitive_ctx: Any,
        tool_results: list[Any] | None = None,
        pending_task: dict[str, Any] | None = None,
        execution_verified: bool = False,
        react_status: str | None = None,
        client: Any = None,
        org_id: str | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> CognitiveLoopTrace:
        if trace.fast_path:
            return trace
        if any(s.stage == "LEARN" and not s.skipped for s in trace.stages):
            return trace
        t_act = time.perf_counter()
        act_evidence = self._act_evidence(
            tool_results=tool_results,
            pending_task=pending_task,
            execution_verified=execution_verified,
            react_status=react_status,
        )
        trace.record("ACT", ok=True, ms=_elapsed_ms(t_act), evidence=act_evidence)

        t_obs = time.perf_counter()
        observe = self._observe(tool_results=tool_results, pending_task=pending_task)
        trace.record("OBSERVE", ok=True, ms=_elapsed_ms(t_obs), evidence=observe)

        t_learn = time.perf_counter()
        learn_meta: dict[str, Any] = {"ok": False}
        try:
            if cognitive_ctx is not None and request is not None:
                from app.services.cognitive_turn_kernel import get_cognitive_turn_kernel

                outcome_event = _outcome_event(
                    execution_verified=execution_verified,
                    pending_task=pending_task,
                    react_status=react_status,
                )
                recommendation_id = str(
                    getattr(cognitive_ctx, "turn_id", None)
                    or conversation_id
                    or trace.loop_id
                )
                await get_cognitive_turn_kernel(self.settings).run_learn(
                    request,
                    cognitive_ctx,
                    act_result={
                        "status": react_status,
                        "success": bool(execution_verified),
                        "action": "execute_task_streaming",
                        "pending": bool(pending_task),
                    },
                    recommendation_id=recommendation_id,
                    outcome_event=outcome_event,
                )
                learn = getattr(cognitive_ctx, "learn", None) or {}
                learn_meta = {
                    "ok": bool(learn.get("ok", True)),
                    "outcome_event": outcome_event,
                    "recommendation_id": recommendation_id,
                    "outcome_ids": list(learn.get("outcome_ids") or []),
                }
            else:
                learn_meta = {"ok": False, "error": "missing_cognitive_context"}
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_loop_learn_failed error=%s", exc)
            learn_meta = {"ok": False, "error": str(exc)[:200]}
        trace.record("LEARN", ok=bool(learn_meta.get("ok")), ms=_elapsed_ms(t_learn), evidence=learn_meta)
        self._emit_completed_audit(
            client=client,
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id,
            trace=trace,
        )
        return trace

    def _observe(
        self,
        *,
        tool_results: list[Any] | None,
        pending_task: dict[str, Any] | None,
    ) -> dict[str, Any]:
        from app.services.write_success_verification import coverage_report, resolve_success_verification

        coverage = coverage_report()
        mutating = _extract_mutating_actions(tool_results)
        verifications: list[dict[str, Any]] = []
        for action in mutating[:12]:
            try:
                ver = resolve_success_verification(action)
                verifications.append(ver.as_dict())
            except Exception:  # noqa: BLE001
                verifications.append({"action": action, "mode": "unresolved"})
        return {
            "coverage_pct": coverage.get("coverage_pct"),
            "mutating_action_count": coverage.get("mutating_action_count"),
            "full_coverage": coverage.get("full_coverage"),
            "this_turn_mutating": mutating,
            "verifications": verifications,
            "pending_approval": bool(pending_task),
            "observe_mode": (
                "follow_up_read_declared"
                if mutating
                else ("awaiting_plan_confirm" if pending_task else "no_mutating_act")
            ),
        }

    @staticmethod
    def _act_evidence(
        *,
        tool_results: list[Any] | None,
        pending_task: dict[str, Any] | None,
        execution_verified: bool,
        react_status: str | None,
    ) -> dict[str, Any]:
        return {
            "tool_result_count": len(tool_results or []),
            "pending_approval": bool(pending_task),
            "execution_verified": bool(execution_verified),
            "react_status": react_status,
        }

    def _emit_completed_audit(
        self,
        *,
        client: Any,
        org_id: str | None,
        user_id: str | None,
        conversation_id: str | None,
        trace: CognitiveLoopTrace,
    ) -> None:
        if client is None or not org_id:
            return
        try:
            from app.workflows.audit import write_audit_event

            write_audit_event(
                client,
                org_id=org_id,
                actor_id=str(user_id or org_id),
                action=AUDIT_ACTION_LOOP_COMPLETED,
                resource_type="conversation" if conversation_id else "cognitive_loop",
                resource_id=str(conversation_id or trace.loop_id),
                metadata={
                    "loopId": trace.loop_id,
                    "turnId": trace.turn_id,
                    "operatorTask": trace.operator_task,
                    "fastPath": trace.fast_path,
                    "spokenMode": trace.spoken_mode,
                    "fullLoop": trace.has_full_loop(),
                    "stages": [
                        {
                            "stage": s.stage,
                            "ok": s.ok,
                            "skipped": s.skipped,
                            "skipReason": s.skip_reason,
                            "ms": s.ms,
                        }
                        for s in trace.stages
                    ],
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("cognitive_loop_audit_skipped error=%s", exc)


def _outcome_event(
    *,
    execution_verified: bool,
    pending_task: dict[str, Any] | None,
    react_status: str | None,
) -> str:
    if execution_verified:
        return "write_verified"
    if pending_task:
        return "plan_awaiting_approval"
    status = str(react_status or "").lower()
    if status in {"ok", "success", "completed"}:
        return "turn_completed"
    if status in {"error", "failed", "fail"}:
        return "turn_failed"
    return "turn_completed"


def _extract_mutating_actions(tool_results: list[Any] | None) -> list[str]:
    actions: list[str] = []
    for row in tool_results or []:
        if isinstance(row, dict):
            name = str(
                row.get("action")
                or row.get("name")
                or row.get("tool")
                or (row.get("function") or {}).get("name")
                or ""
            ).strip()
        else:
            name = str(getattr(row, "name", "") or getattr(row, "action", "") or "").strip()
        if name and name not in actions:
            actions.append(name)
    return actions


_controller: CognitiveLoopController | None = None


def get_cognitive_loop_controller(settings: Settings | None = None) -> CognitiveLoopController:
    global _controller
    if _controller is None or settings is not None:
        _controller = CognitiveLoopController(settings or get_settings())
    return _controller
