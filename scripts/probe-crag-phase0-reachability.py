#!/usr/bin/env python3
"""Phase 0: does the evidence-sufficiency loop actually run on live traffic?

Lesson 4 from the dormant-call audit: measure real reachability with real
production data BEFORE investing a fix-and-prove cycle in a code path. The
sufficiency loop already exists (`evidence_sufficiency_service` +
`unified_turn_knowledge_context`), and it lives on exactly one path -- the
unified-turn prefetch reached via `run_unified_turn_shadow`. The classical
ReAct/fallthrough pipeline never calls it. So before extending it to a
three-way CRAG classification, the question is whether that path carries real
volume and whether the loop genuinely executes when it does.

Lesson 2: distrust the instrument. Two failure modes are indistinguishable if
measured naively:

  * the loop never runs                (real dormancy)
  * the loop runs but is not recorded  (broken instrument)

So this probe does NOT assume where `evidenceSufficiency` sits in the payload.
It walks the whole metadata tree looking for the key, and reports separately:
how many events carry a knowledge block at all, how many of those carry a
sufficiency block, and what the block says. A zero is only reported as real
dormancy when the surrounding structure is present.

Read-only. Queries audit_events; writes one JSON artifact. No model calls, no
writes to any org.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "crag-phase0-reachability.json"
LOOKBACK_DAYS = 30
PAGE = 500

TURN_ACTIONS = (
    "unified_turn.live.completed",
    "unified_turn.live.fallthrough",
    "unified_turn.shadow.completed",
)


def _load_env() -> list[str]:
    """cp1252 env files exist on this machine; a swallowed decode error here
    silently drops every variable and reads as 'not configured'."""
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
            status.append(f"{path.name}: UNREADABLE in all encodings")
            continue
        applied = 0
        for key, value in loaded.items():
            if value and key not in os.environ:
                os.environ[key] = value
                applied += 1
        status.append(f"{path.name}: {applied}/{len(loaded)} applied ({enc})")
    return status


def _find_key(node: Any, target: str, depth: int = 0) -> Any:
    """Depth-first search for a key anywhere in the payload.

    Deliberately not a hardcoded path like
    metadata['latency_breakdown']['unifiedTurnKnowledge']['evidenceSufficiency']:
    if the nesting were renamed, a fixed path would report a confident zero.
    """
    if depth > 8:
        return None
    if isinstance(node, dict):
        if target in node:
            return node[target]
        for value in node.values():
            found = _find_key(value, target, depth + 1)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node[:20]:
            found = _find_key(item, target, depth + 1)
            if found is not None:
                return found
    return None


def _as_meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _fetch(client: Any, action: str, since_iso: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        batch = (
            client.table("audit_events")
            .select("id,org_id,action,created_at,metadata")
            .eq("action", action)
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
            .range(offset, offset + PAGE - 1)
            .execute()
        )
        data = batch.data or []
        rows.extend(data)
        if len(data) < PAGE:
            break
        offset += PAGE
        if offset > 20000:
            break
    return rows


def main() -> int:
    env_status = _load_env()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    since_iso = since.isoformat()

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "env_files": env_status,
        "config_defaults": {
            "evidence_sufficiency_loop_enabled": getattr(
                settings, "evidence_sufficiency_loop_enabled", "MISSING"
            ),
            "evidence_sufficiency_max_rounds": getattr(
                settings, "evidence_sufficiency_max_rounds", "MISSING"
            ),
            "evidence_contradiction_check_enabled": getattr(
                settings, "evidence_contradiction_check_enabled", "MISSING"
            ),
            "unified_turn_live_enabled": getattr(
                settings, "unified_turn_live_enabled", "MISSING"
            ),
            "unified_turn_shadow_enabled": getattr(
                settings, "unified_turn_shadow_enabled", "MISSING"
            ),
        },
        "actions": {},
    }

    # Probe / smoke orgs are excluded from "real traffic" counts. The
    # dormant-call audit found 140 of 142 outcome_error events were probe
    # traffic, so an unsegmented total would have overstated real reach.
    try:
        from isolated_conversation_org import FORBIDDEN_OPERATOR_ORG_ID  # noqa: F401
    except Exception:  # noqa: BLE001
        pass
    probe_org_prefixes = ("f07e57c0-",)

    for action in TURN_ACTIONS:
        rows = _fetch(client, action, since_iso)
        bucket: dict[str, Any] = {
            "total": len(rows),
            "orgs": len({r.get("org_id") for r in rows}),
            "probe_events": 0,
            "real_events": 0,
            "first": rows[-1]["created_at"] if rows else None,
            "last": rows[0]["created_at"] if rows else None,
        }
        # structural presence, so a zero is falsifiable
        has_knowledge = 0
        has_sufficiency = 0
        skipped = Counter()
        bars = Counter()
        rounds = Counter()
        final_suff = Counter()
        stopped = Counter()
        assessors = Counter()
        conflicts_present = 0
        conflict_counts = Counter()
        fallthrough_reasons = Counter()
        # independent cross-check: rounds>0 must coincide with an escalation
        # source appearing in sources_tried, computed by different code
        crosscheck_ok = 0
        crosscheck_bad = 0
        samples: list[dict[str, Any]] = []

        for row in rows:
            org = str(row.get("org_id") or "")
            is_probe = any(org.startswith(p) for p in probe_org_prefixes)
            bucket["probe_events" if is_probe else "real_events"] += 1

            meta = _as_meta(row.get("metadata"))
            know = _find_key(meta, "unifiedTurnKnowledge")
            if isinstance(know, dict):
                has_knowledge += 1
            suff = _find_key(meta, "evidenceSufficiency")
            reason = _find_key(meta, "fallthrough_reason") or _find_key(
                meta, "fallthroughReason"
            )
            if reason:
                fallthrough_reasons[str(reason)] += 1
            conf = _find_key(meta, "evidenceConflicts")
            if isinstance(conf, dict):
                conflicts_present += 1
                conflict_counts[str(conf.get("count"))] += 1

            if not isinstance(suff, dict):
                continue
            has_sufficiency += 1
            skipped[str(suff.get("skipped"))] += 1
            bars[str(suff.get("bar"))] += 1
            used = suff.get("additional_rounds_used")
            rounds[str(used)] += 1
            final_suff[str(suff.get("final_sufficient"))] += 1
            stopped[str(suff.get("stopped_because"))] += 1
            for a in suff.get("assessments") or []:
                if isinstance(a, dict):
                    assessors[str(a.get("assessor"))] += 1

            tried = suff.get("sources_tried") or []
            escalated = [s for s in tried if s in ("internet", "business_graph")]
            try:
                used_n = int(used or 0)
            except (TypeError, ValueError):
                used_n = 0
            if used_n > 0:
                if escalated:
                    crosscheck_ok += 1
                else:
                    crosscheck_bad += 1

            if len(samples) < 3:
                samples.append(
                    {
                        "created_at": row.get("created_at"),
                        "org_is_probe": is_probe,
                        "evidenceSufficiency": suff,
                    }
                )

        bucket.update(
            {
                "events_with_knowledge_block": has_knowledge,
                "events_with_sufficiency_block": has_sufficiency,
                "skipped_reason": dict(skipped),
                "bar": dict(bars),
                "additional_rounds_used": dict(rounds),
                "final_sufficient": dict(final_suff),
                "stopped_because": dict(stopped),
                "assessor": dict(assessors),
                "events_with_conflicts_block": conflicts_present,
                "conflict_count_distribution": dict(conflict_counts),
                "fallthrough_reasons": dict(fallthrough_reasons.most_common()),
                "crosscheck_rounds_vs_sources": {
                    "consistent": crosscheck_ok,
                    "inconsistent": crosscheck_bad,
                },
                "samples": samples,
            }
        )
        report["actions"][action] = bucket

    # A dedicated sufficiency audit action does not exist today; confirm that
    # rather than assume it.
    probe_actions = (
        "evidence.sufficiency.assessed",
        "evidence.sufficiency.escalated",
        "answer.grounding.validated",
    )
    report["named_action_counts"] = {}
    for action in probe_actions:
        try:
            res = (
                client.table("audit_events")
                .select("id", count="exact")
                .eq("action", action)
                .gte("created_at", since_iso)
                .limit(1)
                .execute()
            )
            report["named_action_counts"][action] = getattr(res, "count", None)
        except Exception as exc:  # noqa: BLE001
            report["named_action_counts"][action] = f"ERROR {type(exc).__name__}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print("=" * 66)
    print("PHASE 0 - evidence sufficiency loop reachability")
    print("=" * 66)
    for line in env_status:
        print(f"  env: {line}")
    print()
    print("config on THIS process (not necessarily prod):")
    for k, v in report["config_defaults"].items():
        print(f"  {k:42s} {v}")
    print()
    for action, b in report["actions"].items():
        print("-" * 66)
        print(f"{action}")
        print(f"  events (30d)              : {b['total']}  ({b['real_events']} real / {b['probe_events']} probe)")
        print(f"  distinct orgs             : {b['orgs']}")
        print(f"  window                    : {b['first']} -> {b['last']}")
        print(f"  with knowledge block      : {b['events_with_knowledge_block']}")
        print(f"  with sufficiency block    : {b['events_with_sufficiency_block']}")
        if b["events_with_sufficiency_block"]:
            print(f"  skipped                   : {b['skipped_reason']}")
            print(f"  bar                       : {b['bar']}")
            print(f"  additional_rounds_used    : {b['additional_rounds_used']}")
            print(f"  final_sufficient          : {b['final_sufficient']}")
            print(f"  stopped_because           : {b['stopped_because']}")
            print(f"  assessor                  : {b['assessor']}")
            print(f"  crosscheck rounds/sources : {b['crosscheck_rounds_vs_sources']}")
        print(f"  with conflicts block      : {b['events_with_conflicts_block']} {b['conflict_count_distribution']}")
        if b["fallthrough_reasons"]:
            print(f"  fallthrough reasons       : {b['fallthrough_reasons']}")
    print("-" * 66)
    print(f"named action counts        : {report['named_action_counts']}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
