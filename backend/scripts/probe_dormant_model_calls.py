"""Runtime proof of what production has actually been getting from each dormant site.

The arity mismatch itself is not in question: a positional-argument-count error
is raised before the callee body runs, so these calls cannot intermittently
succeed. What this probe establishes is the part that matters operationally —
what each caller RETURNS once the TypeError is swallowed, because that fallback
value is what production has silently been running on.

Each site is invoked through its real public entry point with realistic input.
No mocks: the point is to observe the real fallback, not a simulated one.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.config import get_settings  # noqa: E402

RESULTS: list[dict] = []


def record(site: str, what_it_should_do: str, observed: object, verdict: str) -> None:
    RESULTS.append(
        {
            "site": site,
            "capability_silently_absent": what_it_should_do,
            "observed_fallback": observed,
            "verdict": verdict,
        }
    )
    print(f"--- {site}")
    print(f"    should do : {what_it_should_do}")
    print(f"    fallback  : {observed}")
    print(f"    verdict   : {verdict}")
    print()


def confirm_raises(fn, *args, **kwargs) -> str:
    """Confirm the factory call itself is the thing that fails."""
    try:
        fn(*args, **kwargs)
        return "DID NOT RAISE"
    except TypeError as exc:
        return f"TypeError: {exc}"
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


async def main() -> int:
    settings = get_settings()

    from app.services.model_router import get_model_router
    from app.services.rag_service import get_rag_service

    print("=== factory signatures (the root fact) ===")
    print(f"get_model_router(settings) -> {confirm_raises(get_model_router, settings)}")
    print(f"get_rag_service(settings)  -> {confirm_raises(get_rag_service, settings)}")
    print()

    # 1. Grounding validator — highest severity: fails OPEN.
    from app.services.answer_validator import validate_grounded_answer

    out = await validate_grounded_answer(
        "Acme signed a $4.2M contract on July 3rd with a 14% discount.",
        [{"content": "Acme is a prospective customer in the pipeline."}],
        org_id=None,
        settings=settings,
    )
    record(
        "answer_validator.validate_grounded_answer:74",
        "detect ungrounded/hallucinated claims against retrieved context",
        out,
        "FAILS OPEN — unsupported answer declared is_valid=True"
        if out.get("is_valid")
        else "fails closed",
    )

    # 2. Conversational turn gate — fails closed into the task pipeline.
    from app.services.conversational_turn_gate import classify_turn_shape

    gate = await classify_turn_shape(message="thanks, that really helped!", settings=settings)
    # A heuristic layer sits in front of the model here, so an obvious greeting
    # never reaches the dormant call. The ambiguous middle is where it matters.
    gate2 = await classify_turn_shape(
        message="how are the deals looking this week", settings=settings
    )
    record(
        "conversational_turn_gate.classify_turn_shape:240",
        "tell genuine small talk apart from casually-phrased data asks",
        {
            "obvious_greeting": {"shape": gate.shape, "used_model": gate.used_model, "reason": gate.reason[:60]},
            "ambiguous_case": {"shape": gate2.shape, "used_model": gate2.used_model, "reason": gate2.reason[:60]},
        },
        "DORMANT — model never consulted on either; heuristics carry every turn"
        if not gate.used_model and not gate2.used_model
        else "model ran",
    )

    # 3. Query rewriter — returns the original query unrewritten.
    from app.services.query_rewriter import rewrite_for_retrieval

    rq = await rewrite_for_retrieval(
        "and what about their renewal?",
        [
            {"role": "user", "content": "Tell me about the Acme account"},
            {"role": "assistant", "content": "Acme is an enterprise customer."},
        ],
        settings=settings,
    )
    record(
        "query_rewriter.refine_query_for_retrieval:52",
        "resolve pronouns into a standalone retrieval query",
        rq,
        "DORMANT — follow-up left unresolved, retrieval sees the raw pronoun"
        if rq.get("refined_query") == rq.get("original_query")
        else "rewrote",
    )

    # 4. Pending reply classifier — comprehension fallback for approvals.
    from app.services.pending_reply_classifier import (
        _model_pending_reply_intent,
        build_pending_snapshot,
    )

    snap = build_pending_snapshot(
        {
            "status": "awaiting_confirmation",
            "action_label": "Create HubSpot contact",
            "invoke_action": "hubspot.contacts.create",
        }
    )
    intent = await _model_pending_reply_intent(
        "yeah go ahead with that one but use the work email",
        snap=snap,
        settings=settings,
        org_id=None,
    )
    record(
        "pending_reply_classifier:500",
        "comprehend approve/reject replies that regex could not classify",
        intent,
        "DORMANT — every regex-unmatched reply collapses to 'ambiguous'"
        if intent == "ambiguous"
        else f"classified {intent}",
    )

    # 4b. Pending plan intent — same shape, different controller.
    from app.services.conversation_turn_controller import _model_pending_intent

    plan_intent = await _model_pending_intent(
        "actually skip the second step",
        current_plan={"goal": "Sync contacts to HubSpot"},
        pending_task={"type": "plan"},
        settings=settings,
        org_id=None,
    )
    record(
        "conversation_turn_controller:273",
        "comprehend continue/modify/cancel replies to a pending plan",
        plan_intent,
        "DORMANT — every reply collapses to 'unclear'"
        if plan_intent == "unclear"
        else f"classified {plan_intent}",
    )

    # 5. Domain intelligence — falls back to keyword rules.
    from app.services.domain_intelligence_service import get_domain_intelligence_service

    dom = get_domain_intelligence_service()
    res = await dom.classify(
        "00000000-0000-0000-0000-000000000000",
        "we need to tighten up how we handle churn risk in the enterprise segment",
    )
    record(
        "domain_intelligence_service:208",
        "model-based business-domain classification over keyword rules",
        {"source": res.get("source"), "department": res.get("department")},
        "DORMANT — rules-only classification, source never 'llm'"
        if res.get("source") != "llm"
        else "model ran",
    )

    # 6. Contextual understanding — goal/constraint extraction.
    from app.services.contextual_understanding_service import (
        get_contextual_understanding_service,
    )

    cu = get_contextual_understanding_service()
    extracted = await cu._model_extract(  # noqa: SLF001
        "get me the churn numbers for enterprise before the board call friday",
        [],
        [],
    )
    record(
        "contextual_understanding_service:225",
        "extract explicit goal + constraints from the message",
        extracted,
        "DORMANT — returns {} so goal/constraints are always empty"
        if extracted == {}
        else "model ran",
    )

    out_path = Path(__file__).resolve().parents[2] / "docs" / "delivery" / "dormant-model-call-runtime-probe.json"
    out_path.write_text(json.dumps(RESULTS, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
