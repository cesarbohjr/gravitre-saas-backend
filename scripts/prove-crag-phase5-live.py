#!/usr/bin/env python3
"""Phase 5: live proof that the CRAG loop's ACTIONS execute in production.

Phase 0 already proved `evidence.sufficiency.assessed` fires. That is not what
this proves. The new capability is what the loop DOES with the verdict --
discard on INCORRECT, refine on CORRECT -- and a green test proves the path
behaves correctly, never that production takes it.

WHAT WOULD MAKE THIS FAIL, stated up front so a pass means something:

  * The loop never engaging. An absent action and a never-reached branch look
    identical from outside, so a turn where the bar comes out casual, or where
    knowledge augmentation is skipped, reports NOT_PROVEN instead of passing.
  * `finalStance` present but `finalStanceInferred=true`. That is a stance
    reconstructed from a legacy bool, not a real three-way classification, and
    counting it would make the whole Phase 1 signal unfalsifiable.
  * The dedicated audit row disagreeing with the nested `evidenceSufficiency`
    block. They are written by different code from the same verdict; agreement
    between two independent records is the evidence, not the existence of a row.

EVIDENCE LABEL: probe-derived, not organic. Real organic volume is honestly low
(36 real turns in the last measured month), so a deliberate probe is the only
way to get a trace today. Both are real evidence; they are not the same claim,
and this program has learned that the difference matters.

The discard and refine branches need an INCORRECT / CORRECT-with-subset verdict
from a real assessor, which cannot be commanded. So they are driven two ways and
reported separately:

  A. ORGANIC-SHAPED: a genuinely hard, multi-hop question on a corpus of one
     chunk. Whatever the assessor decides is recorded as-is.
  B. FORCED: the assessor is stubbed to return INCORRECT, then CORRECT-with-
     subset, so the discard and refinement branches actually execute end to end
     against prod resources. Labelled FORCED everywhere it appears -- it proves
     the machinery runs in the deployed process, not that real traffic triggers
     it.

Safety: isolated conversation smoke org only, guarded against the operator
workspace. `run_unified_turn_shadow` makes model calls and executes no tools.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "crag-phase5-live.json"
PROD_HEALTH = "https://api.gravitre.app/health"
ACTION = "evidence.sufficiency.assessed"

# Multi-hop and evidence-dependent: single-pass retrieval cannot answer it,
# which is the shape Phase 5 asks for. Also regulatory, so the bar is not casual
# and the loop actually engages.
HARD_MESSAGE = (
    "Compare the statutory breach notification deadline for personal health "
    "information in Ontario with the consumer breach notification deadline in "
    "California, and say which one obliges us to notify a regulator sooner and "
    "on what effective date each applies."
)

# Also hard and evidence-dependent, but single-jurisdiction, so the Fabric router
# actually resolves a department and selects a pack. HARD_MESSAGE does not -- see
# `router_gap` in the report -- and a loop with no evidence cannot demonstrate
# what it does with evidence.
ROUTED_MESSAGE = (
    "What are the statutory breach notification deadlines under Ontario privacy "
    "law, and what is the current effective date?"
)

# Conversational: must fast-path and pay for none of the machinery.
SIMPLE_MESSAGE = "thanks, that's helpful"

# Assigned explicitly for the forced branches so evidence definitely exists.
# Forcing a discard on an empty evidence set increments a counter and destroys
# nothing, which is not a proof that the discard works.
FORCED_PACKS = ["pack.legal"]


def _load_env() -> list[str]:
    status: list[str] = []
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            status.append(f"{path.name}: absent")
            continue
        loaded = None
        enc = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded is None:
            status.append(f"{path.name}: UNREADABLE")
            continue
        applied = 0
        for k, v in loaded.items():
            if v and k not in os.environ:
                os.environ[k] = v
                applied += 1
        status.append(f"{path.name}: {applied}/{len(loaded)} ({enc})")
    return status


def _prod_sha() -> str:
    try:
        import urllib.request

        with urllib.request.urlopen(PROD_HEALTH, timeout=20) as resp:
            return str(json.loads(resp.read()).get("git_sha") or "")
    except Exception as exc:  # noqa: BLE001
        return f"unavailable ({type(exc).__name__})"


def _find(node: Any, target: str, depth: int = 0) -> Any:
    if depth > 8:
        return None
    if isinstance(node, dict):
        if target in node:
            return node[target]
        for v in node.values():
            got = _find(v, target, depth + 1)
            if got is not None:
                return got
    elif isinstance(node, list):
        for item in node[:20]:
            got = _find(item, target, depth + 1)
            if got is not None:
                return got
    return None


async def _turn(*, message: str, depth: str, ctx: dict[str, Any]) -> dict[str, Any]:
    from app.services.unified_turn_reasoning_service import run_unified_turn_shadow

    started = time.perf_counter()
    result = await run_unified_turn_shadow(
        org_id=ctx["org_id"],
        user_id=ctx["actor_id"],
        conversation_id=ctx["convo_id"],
        message=message,
        task_state=None,
        conversation_history=None,
        connected_integrations=[],
        client=ctx["client"],
        settings=ctx["settings"],
        reasoning_depth=depth,
    )
    elapsed = round((time.perf_counter() - started) * 1000)
    breakdown = getattr(result, "latency_breakdown", None) or {}
    nested = _find(breakdown, "evidenceSufficiency")
    return {
        "ms": elapsed,
        "outcome_kind": getattr(result, "outcome_kind", None),
        "error": getattr(result, "error", None),
        "nested": nested if isinstance(nested, dict) else None,
    }


async def main() -> int:
    env_status = _load_env()
    os.environ["UNIFIED_TURN_SHADOW_ENABLED"] = "true"
    os.environ["EVIDENCE_SUFFICIENCY_LOOP_ENABLED"] = "true"

    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()
    # Compare prod against the last commit that touched shipped code, not against
    # HEAD. A docs-only commit ahead of prod is not a version mismatch, and
    # failing on it would either block a real proof or, worse, invite someone to
    # relax the check for a reason that is not always true.
    code_sha = subprocess.run(
        [
            "git",
            "log",
            "-1",
            "--format=%H",
            "--",
            "backend/",
            "supabase/",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    ).stdout.strip()
    docs_only_ahead = subprocess.run(
        ["git", "diff", "--name-only", f"{code_sha}..HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
    ).stdout.split()
    prod_sha = _prod_sha()

    from app.config import get_settings
    from app.workflows.repository import get_supabase_client
    from isolated_conversation_org import (
        FORBIDDEN_OPERATOR_ORG_ID,
        mark_smoke_run,
        resolve_isolated_conversation_actor,
    )

    mark_smoke_run()
    settings = get_settings()
    client = get_supabase_client(settings)
    org_id, actor_id, _email = resolve_isolated_conversation_actor(
        dict(os.environ), client
    )
    if str(org_id) == str(FORBIDDEN_OPERATOR_ORG_ID):
        print("REFUSING: resolved the operator workspace, not the isolated org")
        return 2

    convo_id = None
    try:
        rows = (
            client.table("conversations")
            .select("id")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        convo_id = str(rows[0]["id"]) if rows else None
    except Exception:  # noqa: BLE001
        convo_id = None
    if convo_id is None:
        convo_id = str(uuid.uuid4())

    ctx = {
        "org_id": org_id,
        "actor_id": actor_id,
        "convo_id": convo_id,
        "client": client,
        "settings": settings,
    }

    started = datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "started_at": started.isoformat(),
        "local_sha": local_sha[:12],
        "code_sha": code_sha[:12],
        "prod_sha": prod_sha[:12],
        "commits_ahead_of_code_sha": docs_only_ahead,
        "sha_match": code_sha[:12] == prod_sha[:12],
        "env_files": env_status,
        "org_id": org_id,
        "conversation_id": convo_id,
        "evidence_label": "probe-derived (deliberate), NOT organic production volume",
    }
    print(f"local sha : {local_sha[:12]}")
    print(f"code  sha : {code_sha[:12]}  (last commit touching backend/ or supabase/)")
    print(f"prod  sha : {prod_sha[:12]}   match={report['sha_match']}")
    if docs_only_ahead:
        print(f"  ahead of code sha, docs only: {', '.join(docs_only_ahead)}")
    if not report["sha_match"]:
        print("  WARNING: prod is not serving this tip. Every claim below is")
        print("           about the local process, not the deployed one.")
    print()

    # ---- A. organic-shaped hard multi-hop turn --------------------------
    print("A. hard multi-hop turn (organic-shaped, real assessor)")
    hard = await _turn(message=HARD_MESSAGE, depth="full", ctx=ctx)
    report["hard_turn"] = hard
    nested = hard["nested"] or {}
    loop_ran = bool(nested) and not nested.get("skipped")
    report["hard_loop_ran"] = loop_ran
    print(f"   {hard['ms']}ms  outcome={hard['outcome_kind']}")
    if not loop_ran:
        print(f"   loop did not engage (skipped={nested.get('skipped')})")
    else:
        print(
            f"   stance={nested.get('final_stance')} "
            f"inferred={nested.get('final_stance_inferred')} "
            f"rounds={nested.get('additional_rounds_used')} "
            f"discards={nested.get('discards')} refined={nested.get('refined')}"
        )
    print()

    # ---- A2. the routing gap, measured not assumed ----------------------
    # HARD_MESSAGE retrieves nothing. Recorded explicitly, because a loop that
    # iterates twice over an empty evidence set and honestly reports a shortfall
    # is behaving correctly, and reading that as "the loop works on hard queries"
    # would be the mistake.
    from app.knowledge_fabric.router import classify_knowledge_query

    gap: dict[str, Any] = {}
    for label, msg in (("hard_multihop", HARD_MESSAGE), ("routed", ROUTED_MESSAGE)):
        r = classify_knowledge_query(msg, assigned_pack_ids=None, agent_department=None)
        gap[label] = {
            "pack_ids": list(r.pack_ids),
            "departments": list(r.departments),
            "jurisdictions": list(r.jurisdictions),
            "reason": r.reason,
        }
    report["router_gap"] = gap
    print("A2. Fabric routing for each query")
    for label, info in gap.items():
        print(
            f"   {label:14} packs={info['pack_ids']} "
            f"depts={info['departments']} juris={info['jurisdictions']}"
        )
    print()

    # ---- A3. hard-but-routed turn, real assessor, real evidence ---------
    print("A3. hard single-jurisdiction turn (organic-shaped, has evidence)")
    routed = await _turn(message=ROUTED_MESSAGE, depth="full", ctx=ctx)
    rn = routed["nested"] or {}
    report["routed_turn"] = routed
    report["routed_loop_ran"] = bool(rn) and not rn.get("skipped")
    print(f"   {routed['ms']}ms  outcome={routed['outcome_kind']}")
    print(
        f"   stance={rn.get('final_stance')} inferred={rn.get('final_stance_inferred')} "
        f"rounds={rn.get('additional_rounds_used')} discards={rn.get('discards')} "
        f"rows_dropped={rn.get('discarded_rows')} refined={rn.get('refined')}"
    )
    print()

    # ---- B. forced discard and refinement -------------------------------
    # Drives the two new branches through the real function against prod
    # resources. Labelled FORCED: it proves the machinery executes, not that
    # real traffic reaches it.
    print("B. forced branches (assessor stubbed — machinery, not traffic)")
    import app.services.evidence_sufficiency_service as suff
    from app.services.evidence_sufficiency_service import (
        ASSESSOR_LLM,
        STANCE_CORRECT,
        STANCE_INCORRECT,
        SufficiencyVerdict,
    )

    real_assess = suff.assess_evidence_sufficiency
    forced: dict[str, Any] = {}

    def _script(*stances: str, keep: list[int] | None = None):
        seq = list(stances)
        state = {"i": 0}

        async def _assess(*, query, rows, bar, settings=None, org_id=None,
                          routing_tier="multi_step", sources_tried=None):
            stance = seq[min(state["i"], len(seq) - 1)]
            state["i"] += 1
            return SufficiencyVerdict(
                sufficient=stance == STANCE_CORRECT,
                bar=bar,
                assessor=ASSESSOR_LLM,
                reason="FORCED by scripts/prove-crag-phase5-live.py",
                gaps=[] if stance == STANCE_CORRECT else ["does_not_address_question"],
                confidence=0.5,
                stance=stance,
                keep_indices=list(keep or []) if stance == STANCE_CORRECT else [],
            )

        return _assess

    # Driven through `build_unified_turn_knowledge_context` rather than the whole
    # turn, with the pack assigned explicitly. That is the function the mechanism
    # lives in, and it is the only way to guarantee the branches are handed real
    # rows to destroy and refine instead of an empty list.
    from app.services.unified_turn_knowledge_context import (
        build_unified_turn_knowledge_context,
    )

    async def _ctx_turn(message: str) -> dict[str, Any]:
        started_at = time.perf_counter()
        _block, meta = await build_unified_turn_knowledge_context(
            org_id=ctx["org_id"],
            query=message,
            client=ctx["client"],
            settings=ctx["settings"],
            classification={"routing_tier": "multi_step"},
            agent=None,
            knowledge_assignments=[
                {"source_type": "knowledge_pack", "source_id": p, "enabled": True}
                for p in FORCED_PACKS
            ],
            research_scope=None,
            reasoning_depth="full",
            actor_id=ctx["actor_id"],
            conversation_id=None,
        )
        loop = meta.get("evidenceSufficiency") or {}
        return {
            "ms": round((time.perf_counter() - started_at) * 1000),
            "nested": loop,
            "fabric_hits": meta.get("fabric_hit_count"),
        }

    try:
        suff.assess_evidence_sufficiency = _script(STANCE_INCORRECT, STANCE_CORRECT)
        r = await _ctx_turn(HARD_MESSAGE)
        n = r["nested"]
        forced["discard"] = {
            "ms": r["ms"],
            "fabric_hits": r["fabric_hits"],
            "loop_ran": bool(n) and not n.get("skipped"),
            "discards": n.get("discards"),
            "discarded_rows": n.get("discarded_rows"),
            "final_stance": n.get("final_stance"),
            "stances": n.get("stances"),
        }
        print(
            f"   discard : evidence={r['fabric_hits']} discards={n.get('discards')} "
            f"rows_destroyed={n.get('discarded_rows')} stances={n.get('stances')}"
        )

        suff.assess_evidence_sufficiency = _script(STANCE_CORRECT, keep=[0])
        r = await _ctx_turn(HARD_MESSAGE)
        n = r["nested"]
        forced["refine"] = {
            "ms": r["ms"],
            "fabric_hits": r["fabric_hits"],
            "loop_ran": bool(n) and not n.get("skipped"),
            "refined": n.get("refined"),
            "refined_from": n.get("refined_from"),
            "refined_to": n.get("refined_to"),
            "final_stance": n.get("final_stance"),
        }
        print(
            f"   refine  : evidence={r['fabric_hits']} refined={n.get('refined')} "
            f"{n.get('refined_from')} -> {n.get('refined_to')} rows"
        )
    finally:
        suff.assess_evidence_sufficiency = real_assess
    report["forced_branches"] = forced
    print()

    # ---- C. simple turn: latency tiering --------------------------------
    print("C. conversational turn (must pay for none of it)")
    simple = await _turn(message=SIMPLE_MESSAGE, depth="conversational", ctx=ctx)
    sn = simple["nested"] or {}
    report["simple_turn"] = {
        "ms": simple["ms"],
        # Absent block and present-but-skipped are different facts.
        "sufficiency_block_present": bool(simple["nested"]),
        "skipped": sn.get("skipped"),
        "assessments": len(sn.get("assessments") or []),
        "discards": sn.get("discards"),
    }
    print(
        f"   {simple['ms']}ms  skipped={sn.get('skipped')} "
        f"assessor_calls={len(sn.get('assessments') or [])}"
    )
    print()

    # ---- D. read the audit rows back out of prod ------------------------
    await asyncio.sleep(2)
    since = (started - timedelta(minutes=3)).isoformat()
    rows = (
        client.table("audit_events")
        .select("id,action,created_at,metadata")
        .eq("action", ACTION)
        .eq("org_id", org_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )
    report["audit_rows_found"] = len(rows)
    report["audit_rows"] = [
        {
            "created_at": r.get("created_at"),
            "finalStance": (r.get("metadata") or {}).get("finalStance"),
            "finalStanceInferred": (r.get("metadata") or {}).get("finalStanceInferred"),
            "stances": (r.get("metadata") or {}).get("stances"),
            "discards": (r.get("metadata") or {}).get("discards"),
            "refined": (r.get("metadata") or {}).get("refined"),
            "assessorRan": (r.get("metadata") or {}).get("assessorRan"),
        }
        for r in rows
    ]
    print(f"D. audit rows in prod (last 3 min): {len(rows)}")
    for r in report["audit_rows"]:
        print(
            f"   {r['created_at']}  stance={r['finalStance']} "
            f"inferred={r['finalStanceInferred']} discards={r['discards']} "
            f"refined={r['refined']}"
        )
    print()

    # ---- verdict --------------------------------------------------------
    checks: dict[str, Any] = {}
    checks["prod_serves_this_tip"] = report["sha_match"]
    checks["hard_turn_engaged_the_loop"] = report["hard_loop_ran"]
    checks["routed_turn_engaged_the_loop"] = report["routed_loop_ran"]
    # A conversational turn must stay in the same order of magnitude it was
    # before this work. The loop turns run ~18s; a simple turn near that would
    # mean the tiering leaked.
    checks["simple_turn_latency_unregressed"] = report["simple_turn"]["ms"] < 3000

    stanced = [
        r for r in report["audit_rows"] if r["finalStance"] not in (None, "")
    ]
    checks["audit_carries_a_stance"] = bool(stanced)
    # A stance reconstructed from a legacy bool is not a three-way
    # classification. Counting it would make the Phase 1 signal unfalsifiable.
    checks["stance_is_reasoned_not_inferred"] = any(
        r["finalStanceInferred"] is False for r in stanced
    )
    # Both branches must have destroyed or dropped REAL rows. A discard counter
    # incrementing over an empty evidence set proves the line executed and
    # nothing else; the first run of this probe passed exactly that way.
    fd = forced.get("discard") or {}
    checks["forced_discard_destroyed_rows"] = bool(fd.get("discarded_rows"))
    fr = forced.get("refine") or {}
    checks["forced_refine_narrowed_rows"] = (
        fr.get("refined") is True
        and isinstance(fr.get("refined_from"), int)
        and isinstance(fr.get("refined_to"), int)
        and fr["refined_to"] < fr["refined_from"]
    )
    # The property is "a conversational turn pays for none of it", not "skipped
    # equals a particular string". A turn that never reaches knowledge
    # augmentation emits no sufficiency block at all, and asserting the specific
    # mechanism failed a turn that was in fact free.
    st = report["simple_turn"]
    checks["simple_turn_paid_for_none_of_it"] = (
        st["assessments"] == 0
        and not st.get("discards")
        and st["skipped"] in (None, "casual_bar", "not_informational")
    )

    # Cross-check: the dedicated row and the nested block are written by
    # different code from the same verdict. Disagreement means one instrument is
    # lying, and a confident wrong number is worse than none.
    nested_stance = (hard["nested"] or {}).get("final_stance")
    row_stances = [r["finalStance"] for r in stanced]
    checks["nested_and_row_agree"] = (
        bool(nested_stance) and nested_stance in row_stances
    )

    report["checks"] = checks
    hard_blockers = [
        k
        for k in ("prod_serves_this_tip", "hard_turn_engaged_the_loop",
                  "audit_carries_a_stance", "stance_is_reasoned_not_inferred")
        if not checks.get(k)
    ]
    if hard_blockers:
        report["verdict"] = "NOT_PROVEN: " + ", ".join(hard_blockers)
    elif all(checks.values()):
        report["verdict"] = "PASS (probe-derived)"
    else:
        report["verdict"] = "PARTIAL: " + ", ".join(
            k for k, v in checks.items() if not v
        )

    print("checks:")
    for k, v in checks.items():
        print(f"   {'PASS' if v else 'FAIL'}  {k}")
    print()
    print(f"VERDICT: {report['verdict']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
