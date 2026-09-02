#!/usr/bin/env python3
"""Live proof that evidence.sufficiency.assessed genuinely lands in production.

Phase 0 measured this action at 0 events over 30 days because it did not exist.
This drives a real, evidence-dependent unified turn against prod resources, then
reads the row back out of prod `audit_events` and checks it against an
independent signal.

Why the cross-check matters (lesson 2): the new event and the pre-existing
nested `evidenceSufficiency` block inside `unified_turn.*` are written by
different code from the same verdict. If the dedicated event disagrees with the
nested block on the same turn, the new instrument is wrong -- and an instrument
that reports a confident, wrong value is worse than none. Agreement between two
independently-written records is the actual evidence here, not the mere
existence of a row.

The verdict is deliberately falsifiable. A run where the loop never engages
reports NOT_PROVEN rather than passing quietly, because an absent row and a
never-executed gate look identical from the outside -- which is precisely the
Class C mistake this program has now booked four times.

Safety: runs in the isolated conversation smoke org, guarded against ever being
a customer org. `run_unified_turn_shadow` makes model calls and does not execute
tools, so no connector write can occur. The only prod write is the audit row
this proof is about.
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

OUT = REPO / "docs" / "delivery" / "sufficiency-audit-live.json"
PROD_HEALTH = "https://api.gravitre.app/health"
ACTION = "evidence.sufficiency.assessed"

# Regulatory-shaped and informational: must clear
# should_augment_unified_turn_with_knowledge AND land on a non-casual bar, or
# the loop correctly skips and the probe proves nothing.
MESSAGE = (
    "What are the statutory breach notification deadlines under Ontario privacy "
    "law, and what is the current effective date?"
)


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


async def main() -> int:
    env_status = _load_env()
    os.environ["UNIFIED_TURN_SHADOW_ENABLED"] = "true"
    os.environ["EVIDENCE_SUFFICIENCY_LOOP_ENABLED"] = "true"

    import subprocess

    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()

    from app.config import get_settings
    from app.services.unified_turn_reasoning_service import run_unified_turn_shadow
    from app.workflows.repository import get_supabase_client
    from isolated_conversation_org import (
        FORBIDDEN_OPERATOR_ORG_ID,
        mark_smoke_run,
        resolve_isolated_conversation_actor,
    )

    mark_smoke_run()
    settings = get_settings()
    client = get_supabase_client(settings)
    org_id, actor_id, _email = resolve_isolated_conversation_actor(dict(os.environ), client)
    if str(org_id) == str(FORBIDDEN_OPERATOR_ORG_ID):
        print("REFUSING: resolved the operator workspace, not the isolated org")
        return 2

    # Reuse a real conversation row so resource_id is a genuine reference rather
    # than a synthetic UUID that happens to satisfy the format check.
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

    started = datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "started_at": started.isoformat(),
        "local_sha": local_sha[:12],
        "prod_sha": _prod_sha()[:12],
        "env_files": env_status,
        "org_id": org_id,
        "actor_id": actor_id,
        "conversation_id": convo_id,
        "conversation_was_synthetic": synthetic_convo,
        "message": MESSAGE,
        "action": ACTION,
    }

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
        reasoning_depth="full",
    )

    breakdown = getattr(result, "latency_breakdown", None) or {}
    nested = _find(breakdown, "evidenceSufficiency")
    report["outcome_kind"] = getattr(result, "outcome_kind", None)
    report["turn_error"] = getattr(result, "error", None)
    report["nested_block_present"] = isinstance(nested, dict)
    report["nested_evidenceSufficiency"] = nested

    loop_ran = isinstance(nested, dict) and not nested.get("skipped")
    report["loop_ran"] = loop_ran
    if isinstance(nested, dict):
        report["loop_skipped_reason"] = nested.get("skipped")

    # Read the row back out of prod.
    await asyncio.sleep(2)
    since = (started - timedelta(minutes=2)).isoformat()
    rows = (
        client.table("audit_events")
        .select("id,org_id,actor_id,action,resource_type,resource_id,created_at,metadata")
        .eq("action", ACTION)
        .eq("org_id", org_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    report["rows_found"] = len(rows)
    report["row"] = rows[0] if rows else None

    checks: dict[str, Any] = {}
    if not loop_ran:
        # An absent row and a gate that never ran are indistinguishable from
        # outside. Say so rather than reporting a pass.
        report["verdict"] = "NOT_PROVEN_loop_did_not_engage"
        checks["loop_engaged"] = False
    elif not rows:
        report["verdict"] = "FAIL_no_audit_row"
        checks["loop_engaged"] = True
        checks["row_written"] = False
    else:
        row = rows[0]
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}

        checks["loop_engaged"] = True
        checks["row_written"] = True
        checks["real_actor_recorded"] = str(row.get("actor_id")) == str(actor_id)
        checks["resource_is_the_conversation"] = str(row.get("resource_id")) == str(convo_id)
        checks["resource_type"] = row.get("resource_type") == "conversation"

        # The independent cross-check: the dedicated event must agree with the
        # nested block, which is written by different code from the same verdict.
        checks["agrees_on_bar"] = meta.get("bar") == nested.get("bar")
        checks["agrees_on_final_sufficient"] = meta.get("finalSufficient") == nested.get(
            "final_sufficient"
        )
        checks["agrees_on_rounds"] = meta.get("additionalRoundsUsed") == nested.get(
            "additional_rounds_used"
        )
        checks["agrees_on_stopped_because"] = meta.get("stoppedBecause") == nested.get(
            "stopped_because"
        )

        # assessorRan must be consistent with the raw assessor list it was
        # derived from, so the field is not trusted on its own.
        assessors = meta.get("assessors") or []
        checks["assessor_list_present"] = bool(assessors)
        checks["assessorRan_matches_raw_list"] = meta.get("assessorRan") == (
            "llm" in assessors
        )
        checks["assessorUnavailable_matches_raw_list"] = meta.get(
            "assessorUnavailable"
        ) == ("assessor_error" in assessors)
        checks["evidence_counts_present"] = isinstance(meta.get("evidenceCounts"), dict)

        report["audit_metadata"] = meta
        report["verdict"] = "PASS" if all(
            v is True for k, v in checks.items() if isinstance(v, bool)
        ) else "FAIL_checks"

    report["checks"] = checks
    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    existing: list[dict[str, Any]] = []
    if OUT.is_file():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
            existing = prev if isinstance(prev, list) else [prev]
        except json.JSONDecodeError:
            existing = []
    existing.append(report)
    OUT.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")

    print("=" * 68)
    print("LIVE PROOF - evidence.sufficiency.assessed")
    print("=" * 68)
    for line in env_status:
        print(f"  env              : {line}")
    print(f"  local sha        : {report['local_sha']}")
    print(f"  prod sha         : {report['prod_sha']}")
    print(f"  org              : {org_id}")
    print(f"  conversation     : {convo_id}{' (synthetic)' if synthetic_convo else ''}")
    print(f"  outcome_kind     : {report['outcome_kind']}")
    print(f"  turn error       : {report['turn_error']}")
    print(f"  loop ran         : {loop_ran} (skipped={report.get('loop_skipped_reason')})")
    print(f"  rows found       : {report['rows_found']}")
    print()
    for k, v in checks.items():
        mark = "ok  " if v is True else ("FAIL" if v is False else "    ")
        print(f"  [{mark}] {k} = {v}")
    print()
    if report.get("audit_metadata"):
        m = report["audit_metadata"]
        print(f"  recorded verdict : bar={m.get('bar')} sufficient={m.get('finalSufficient')} "
              f"rounds={m.get('additionalRoundsUsed')} stopped={m.get('stoppedBecause')}")
        print(f"  assessors        : {m.get('assessors')} ran={m.get('assessorRan')} "
              f"unavailable={m.get('assessorUnavailable')}")
        print(f"  evidence counts  : {m.get('evidenceCounts')}")
    print()
    print(f"  VERDICT          : {report['verdict']}")
    print(f"  wrote {OUT}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
