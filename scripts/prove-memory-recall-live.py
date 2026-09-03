#!/usr/bin/env python3
"""Live proof that the per-turn memory recall signal reaches production.

The memory census could not answer "did memory reach this answer" at all. It
reported `no_memory_signal` on 1581 of 1581 turns and first published that as
"0 turns recalled memory" -- the same sentence for a blind instrument and for a
genuinely unused subsystem. This proves the two new signals distinguish them.

Two independently-written records of the same fact, per lesson 2:

  * `memory.recalled` in prod `audit_events`, written by the kernel emitter.
  * `unifiedTurnKnowledge.memoryRecall` on the `unified_turn.*` event, written
    by the prompt-assembly merge in a different module.

If those two disagree about how many memories a single turn recalled, the new
instrument is wrong -- and a confident wrong number is worse than none. The
existence of a row proves nothing on its own; agreement does.

The verdict is deliberately falsifiable in both directions:

  * recall total 0 and not degraded -> NOT_PROVEN, because a zero-recall turn is
    *supposed* to write no `memory.recalled` row, so its absence proves nothing.
  * the zero case is still checked, via the always-on nested block, since
    "reports honestly at zero" is the actual claim being made.

Safety: isolated conversation smoke org, hard-refused against the operator
workspace. `run_unified_turn_shadow` makes model calls and executes no tools, so
no connector write can occur. Writes: the audit rows under proof, and -- only if
the org has no memories to recall -- one seeded memory row via the real
promotion service, which is recorded in the report as `seeded`.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
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

OUT = REPO / "docs" / "delivery" / "memory-recall-live.json"
PROD_HEALTH = "https://api.gravitre.app/health"
ACTION = "memory.recalled"

# Distinctive enough that a hit is attributable to the seeded row rather than to
# incidental similarity, and phrased as a decision so it lands in a real bucket.
SEED_CONTENT = (
    "Standing decision: quarterly business reviews are scheduled by the "
    "Gravitre memory recall probe and always run on the first Tuesday."
)
MESSAGE = "When do our quarterly business reviews run, and who schedules them?"


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


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


async def main() -> int:  # noqa: C901
    env_status = _load_env()
    os.environ["UNIFIED_TURN_SHADOW_ENABLED"] = "true"

    import subprocess

    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()

    from app.config import get_settings
    from app.services.cognitive_turn_kernel import (
        AUDIT_ACTION_MEMORY_RECALL,
        CognitiveTurnKernel,
        CognitiveTurnRequest,
        memory_recall_signal,
    )
    from app.services.unified_turn_reasoning_service import (
        emit_unified_turn_shadow_audit,
        run_unified_turn_shadow,
    )
    from app.workflows.repository import get_supabase_client
    from isolated_conversation_org import (
        FORBIDDEN_OPERATOR_ORG_ID,
        mark_smoke_run,
        resolve_isolated_conversation_actor,
    )

    assert AUDIT_ACTION_MEMORY_RECALL == ACTION, "action constant drifted from this probe"

    mark_smoke_run()
    settings = get_settings()
    client = get_supabase_client(settings)
    org_id, actor_id, _email = resolve_isolated_conversation_actor(dict(os.environ), client)
    if str(org_id) == str(FORBIDDEN_OPERATOR_ORG_ID):
        print("REFUSING: resolved the operator workspace, not the isolated org")
        return 2

    report: dict[str, Any] = {
        "local_sha": local_sha[:12],
        "prod_sha": _prod_sha()[:12],
        "env_files": env_status,
        "org_id": org_id,
        "actor_id": actor_id,
        "action": ACTION,
        "message": MESSAGE,
    }

    # --- an agent and a conversation, both real rows -----------------------
    agent_id = None
    try:
        rows = (
            client.table("agents").select("id").eq("org_id", org_id).limit(1).execute().data
            or []
        )
        agent_id = str(rows[0]["id"]) if rows else None
    except Exception:  # noqa: BLE001
        agent_id = None

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
    synthetic_convo = convo_id is None
    if convo_id is None:
        convo_id = str(uuid.uuid4())
    report["agent_id"] = agent_id
    report["conversation_id"] = convo_id
    report["conversation_was_synthetic"] = synthetic_convo

    # --- something to recall ----------------------------------------------
    existing = (
        client.table("agent_memories")
        .select("id,content,category,provenance")
        .eq("org_id", org_id)
        .limit(50)
        .execute()
        .data
        or []
    )
    report["memories_before"] = len(existing)
    report["seeded"] = False
    if not any(SEED_CONTENT[:60] in str(r.get("content") or "") for r in existing):
        from app.services.workspace_memory_service import promote_turn_memories

        written = promote_turn_memories(
            client,
            org_id=org_id,
            memories=[{"content": SEED_CONTENT, "category": "decision"}],
            agent_id=agent_id,
            conversation_id=convo_id,
            user_id=actor_id,
            settings=settings,
            provenance="memory_recall_live_proof",
        )
        report["seeded"] = bool(written)
        report["seeded_rows"] = len(written or [])
        # Embedding/index settle.
        await asyncio.sleep(2)

    started = datetime.now(timezone.utc)
    report["started_at"] = started.isoformat()

    # --- 1. the kernel turn: produces the signal and emits memory.recalled --
    kernel = CognitiveTurnKernel(settings)
    ctx = await kernel.run_pre_act(
        CognitiveTurnRequest(
            org_id=org_id,
            message=MESSAGE,
            user_id=actor_id,
            agent_id=agent_id,
            conversation_id=convo_id,
            surface="ai_chat",
            entry_point="memory_recall_live_proof",
            client=client,
        )
    )
    in_process = memory_recall_signal(ctx)
    report["in_process_signal"] = in_process
    report["cognitive_turn_id"] = ctx.turn_id

    # --- 2. the unified turn: merges memoryRecall into its audit meta -------
    result = await run_unified_turn_shadow(
        org_id=org_id,
        user_id=actor_id,
        conversation_id=convo_id,
        message=MESSAGE,
        task_state=None,
        conversation_history=None,
        connected_integrations=[],
        client=client,
        settings=settings,
        cognitive_context=ctx,
        reasoning_depth="full",
    )
    report["outcome_kind"] = getattr(result, "outcome_kind", None)
    report["turn_error"] = getattr(result, "error", None)
    nested_in_process = _find(getattr(result, "latency_breakdown", None) or {}, "memoryRecall")
    report["nested_in_process"] = nested_in_process

    emit_unified_turn_shadow_audit(
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        conversation_id=convo_id,
        result=result,
    )

    # --- 3. read both back out of prod -------------------------------------
    await asyncio.sleep(3)
    since = (started - timedelta(minutes=2)).isoformat()

    window_rows = (
        client.table("audit_events")
        .select("id,org_id,actor_id,action,resource_type,resource_id,created_at,metadata")
        .eq("action", ACTION)
        .eq("org_id", org_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    # Attributed by turn id, not by time window. The first run of this probe
    # counted three rows in one window -- two probe turns plus a real
    # `execute_task_streaming` turn -- and reported a double emission that had
    # not happened. Rows from other turns are reported separately, as
    # corroboration rather than contamination.
    recall_rows = [
        r
        for r in window_rows
        if str(_as_dict(r.get("metadata")).get("cognitiveTurnId") or "") == str(ctx.turn_id)
    ]
    other_rows = [r for r in window_rows if r not in recall_rows]
    report["window_rows_found"] = len(window_rows)
    report["other_turn_rows"] = [
        {
            "created_at": r.get("created_at"),
            "entryPoint": _as_dict(r.get("metadata")).get("entryPoint"),
            "total": _as_dict(r.get("metadata")).get("total"),
        }
        for r in other_rows
    ]
    turn_rows = (
        client.table("audit_events")
        .select("id,action,created_at,metadata")
        .in_(
            "action",
            [
                "unified_turn.live.completed",
                "unified_turn.live.fallthrough",
                "unified_turn.shadow.completed",
            ],
        )
        .eq("org_id", org_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    report["recall_rows_found"] = len(recall_rows)
    report["turn_rows_found"] = len(turn_rows)
    report["row"] = recall_rows[0] if recall_rows else None

    nested_from_db = None
    for row in turn_rows:
        nested_from_db = _find(_as_dict(row.get("metadata")), "memoryRecall")
        if nested_from_db is not None:
            report["turn_row_action"] = row.get("action")
            break
    report["nested_from_db"] = nested_from_db

    checks: dict[str, Any] = {}
    total = int(in_process.get("total") or 0)
    degraded = bool(in_process.get("degraded"))

    # The always-on signal is checked regardless of whether anything was
    # recalled -- "reports honestly at zero" is the claim.
    checks["recall_ran"] = bool(in_process.get("ran"))
    checks["nested_block_reached_prod"] = isinstance(nested_from_db, dict)
    if isinstance(nested_from_db, dict):
        checks["nested_agrees_on_total"] = int(nested_from_db.get("total") or 0) == total
        checks["nested_agrees_on_ran"] = bool(nested_from_db.get("ran")) == bool(
            in_process.get("ran")
        )
        checks["nested_agrees_on_degraded"] = bool(nested_from_db.get("degraded")) == degraded
        checks["nested_carries_per_source"] = isinstance(nested_from_db.get("bySource"), dict)

    if not (total or degraded):
        # Honest: with nothing recalled, no memory.recalled row is expected, so
        # its absence is not evidence of anything.
        checks["memory_recalled_row_expected"] = False
        report["verdict"] = (
            "PARTIAL_nested_only_no_recall"
            if all(v is True for v in checks.values() if isinstance(v, bool))
            else "FAIL_checks"
        )
    elif not recall_rows:
        checks["memory_recalled_row_expected"] = True
        checks["memory_recalled_row_written"] = False
        report["verdict"] = "FAIL_no_audit_row"
    else:
        row = recall_rows[0]
        meta = _as_dict(row.get("metadata"))
        checks["memory_recalled_row_expected"] = True
        checks["memory_recalled_row_written"] = True
        checks["exactly_one_row_for_this_turn"] = len(recall_rows) == 1
        checks["row_is_attributed_to_this_turn"] = str(
            meta.get("cognitiveTurnId")
        ) == str(ctx.turn_id)
        checks["real_actor_recorded"] = str(row.get("actor_id")) == str(actor_id)
        checks["resource_is_the_conversation"] = str(row.get("resource_id")) == str(convo_id)
        checks["resource_type"] = row.get("resource_type") == "conversation"

        # The cross-check that actually carries the proof.
        checks["row_agrees_with_in_process_total"] = int(meta.get("total") or 0) == total
        checks["row_agrees_with_in_process_degraded"] = bool(meta.get("degraded")) == degraded
        if isinstance(nested_from_db, dict):
            checks["row_agrees_with_nested_total"] = int(meta.get("total") or 0) == int(
                nested_from_db.get("total") or 0
            )
        # Per-source counts must sum to the reported total, so `total` is not
        # trusted on its own.
        by_source = meta.get("bySource") or {}
        checks["per_source_sums_to_total"] = (
            isinstance(by_source, dict)
            and sum(int(v or 0) for v in by_source.values()) == int(meta.get("total") or 0)
        )
        checks["attempted_sources_recorded"] = bool(meta.get("attempted"))
        report["audit_metadata"] = meta
        report["verdict"] = (
            "PASS"
            if all(v is True for v in checks.values() if isinstance(v, bool))
            else "FAIL_checks"
        )

    report["checks"] = checks
    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    prior: list[dict[str, Any]] = []
    if OUT.is_file():
        try:
            loaded = json.loads(OUT.read_text(encoding="utf-8"))
            prior = loaded if isinstance(loaded, list) else [loaded]
        except json.JSONDecodeError:
            prior = []
    prior.append(report)
    OUT.write_text(json.dumps(prior, indent=2, default=str), encoding="utf-8")

    print("=" * 70)
    print("LIVE PROOF - memory.recalled + unifiedTurnKnowledge.memoryRecall")
    print("=" * 70)
    for line in env_status:
        print(f"  env            : {line}")
    print(f"  local sha      : {report['local_sha']}")
    print(f"  prod sha       : {report['prod_sha']}")
    print(f"  org            : {org_id}")
    print(f"  agent          : {agent_id}")
    print(f"  conversation   : {convo_id}{' (synthetic)' if synthetic_convo else ''}")
    print(f"  memories before: {report['memories_before']}  seeded={report['seeded']}")
    print(f"  outcome_kind   : {report['outcome_kind']}  error={report['turn_error']}")
    print()
    print(f"  in-process     : {in_process}")
    print(f"  nested (prod)  : {nested_from_db}")
    print(f"  turn id        : {ctx.turn_id}")
    print(f"  rows this turn : {report['recall_rows_found']} "
          f"(of {report['window_rows_found']} in window)")
    for other in report["other_turn_rows"]:
        print(f"    other turn   : {other['created_at']} entry={other['entryPoint']} "
              f"total={other['total']}")
    print()
    for k, v in checks.items():
        mark = "ok  " if v is True else ("FAIL" if v is False else "    ")
        print(f"  [{mark}] {k} = {v}")
    print()
    if report.get("audit_metadata"):
        m = report["audit_metadata"]
        print(f"  recorded       : total={m.get('total')} bySource={m.get('bySource')}")
        print(f"                   attempted={m.get('attempted')} degraded={m.get('degraded')}")
    print()
    print(f"  VERDICT        : {report['verdict']}")
    print(f"  wrote {OUT}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
