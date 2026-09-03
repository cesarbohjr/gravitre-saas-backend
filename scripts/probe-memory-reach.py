#!/usr/bin/env python3
"""Real reachability census for the memory subsystem, before hardening it.

Prompt 1 (CRAG) and Prompt 2 (Context Engine) were deferred because the paths
they would improve carry no real traffic: 36 real turns in 30 days and one RAG
chunk platform-wide. Prompt 3 (memory hardening) is argued to be different --
its value is said not to depend on retrieval volume the way theirs does.

That argument is plausible and is exactly the kind that lesson 4 exists to test
rather than accept. Memory has its own volume question: rows written, rows
recalled into real turns, and promotion candidates actually adjudicated. This
measures all three before any hardening is scoped.

Deliberately separates probe-org traffic from real-org traffic. The CRAG audit
found 256 of 256 sufficiency-loop runs were this program's own probes, and an
unsegmented aggregate would have read as healthy usage.

Read-only. No writes, no model calls.
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

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = REPO / "docs" / "delivery" / "memory-reach-census.json"
LOOKBACK_DAYS = 30
PAGE = 500

# Orgs whose traffic is this program's own instrumentation, not customers.
PROBE_ORG_MARKERS = ("smoke", "isolated conversation", "probe")


def _load_env() -> list[str]:
    """Load env files across real encodings, reporting what applied.

    These files are cp1252 on this machine. An earlier probe used the dotenv
    default, swallowed UnicodeDecodeError per file, and reported a missing API
    key -- a parse failure read as a clean negative.
    """
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
        status.append(f"{path.name}: {applied} of {len(loaded)} applied ({enc})")
    return status


def _meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _find(node: Any, target: str, depth: int = 0) -> Any:
    """Search the payload tree, not a fixed path.

    A renamed nesting must read as a miss to be investigated, never as a zero
    to be believed.
    """
    if depth > 8:
        return None
    if isinstance(node, dict):
        if target in node:
            return node[target]
        for value in node.values():
            got = _find(value, target, depth + 1)
            if got is not None:
                return got
    elif isinstance(node, list):
        for item in node[:20]:
            got = _find(item, target, depth + 1)
            if got is not None:
                return got
    return None


def _fetch_all(client: Any, table: str, columns: str) -> tuple[list[dict[str, Any]], str | None]:
    """Return (rows, error). Never a sentinel row mixed into real data.

    The first version returned ``[{"__error__": ...}]`` on failure, so a
    connection error was counted as one organization and printed as
    ``organizations: 1``. A failed read must be unavailable, never a number --
    that is the Class B mistake this program has already paid for twice.
    """
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        try:
            batch = (
                client.table(table)
                .select(columns)
                .range(offset, offset + PAGE - 1)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            return [], f"{type(exc).__name__}: {exc}"
        data = batch.data or []
        rows.extend(data)
        if len(data) < PAGE:
            return rows, None
        offset += PAGE


def _is_probe(name: str) -> bool:
    lowered = (name or "").lower()
    return any(marker in lowered for marker in PROBE_ORG_MARKERS)


def main() -> int:
    env_status = _load_env()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(get_settings())
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "env_status": env_status,
    }

    errors: dict[str, str] = {}

    orgs, err = _fetch_all(client, "organizations", "id,name,created_at")
    if err:
        errors["organizations"] = err
    names = {str(o.get("id")): str(o.get("name") or "") for o in orgs if "id" in o}
    report["org_count"] = "UNAVAILABLE" if err else len(orgs)

    # ---- 1. what is stored -------------------------------------------------
    memories, err = _fetch_all(
        client,
        "agent_memories",
        "id,org_id,agent_id,category,provenance,confidence,is_active,created_at,created_by",
    )
    if err:
        errors["agent_memories"] = err

    by_org: dict[str, Counter] = {}
    categories: Counter = Counter()
    provenances: Counter = Counter()
    for row in memories:
        org = str(row.get("org_id"))
        by_org.setdefault(org, Counter())
        by_org[org]["rows"] += 1
        by_org[org]["active" if row.get("is_active") else "inactive"] += 1
        if row.get("agent_id"):
            by_org[org]["agent_scoped"] += 1
        else:
            by_org[org]["workspace_scoped"] += 1
        categories[str(row.get("category"))] += 1
        prov = str(row.get("provenance") or "")
        provenances[prov.split(":")[0] or "<none>"] += 1

    report["agent_memories_total"] = (
        "UNAVAILABLE" if "agent_memories" in errors else len(memories)
    )
    report["agent_memories_by_category"] = dict(categories.most_common())
    report["agent_memories_by_provenance_prefix"] = dict(provenances.most_common())
    report["agent_memories_by_org"] = {
        org: {
            "org_name": names.get(org, "<unknown>"),
            "is_probe_org": _is_probe(names.get(org, "")),
            **dict(counts),
        }
        for org, counts in sorted(by_org.items(), key=lambda kv: -kv[1]["rows"])
    }
    report["agent_memories_in_real_orgs"] = (
        "UNAVAILABLE"
        if "agent_memories" in errors
        else sum(
            info["rows"]
            for info in report["agent_memories_by_org"].values()
            if not info["is_probe_org"]
        )
    )

    stamps = sorted(str(r.get("created_at")) for r in memories if r.get("created_at"))
    report["agent_memories_created_range"] = (
        {"earliest": stamps[0], "latest": stamps[-1]} if stamps else None
    )

    # ---- 2. the promotion pipeline ----------------------------------------
    candidates, err = _fetch_all(
        client,
        "memory_promotion_candidates",
        "id,org_id,status,created_at",
    )
    if err:
        errors["memory_promotion_candidates"] = err
    cand_status: Counter = Counter()
    cand_org: Counter = Counter()
    for row in candidates:
        cand_status[str(row.get("status"))] += 1
        cand_org[names.get(str(row.get("org_id")), "<unknown>")] += 1
    report["memory_promotion_candidates_total"] = (
        "UNAVAILABLE" if "memory_promotion_candidates" in errors else len(candidates)
    )
    report["memory_promotion_candidates_by_status"] = dict(cand_status.most_common())
    report["memory_promotion_candidates_by_org"] = dict(cand_org.most_common())

    # select * deliberately: this table has no created_at, and naming a column
    # that does not exist returns a 42703 APIError that reads like a failed probe
    # rather than an empty table.
    promo_audit, err = _fetch_all(client, "agent_memory_promotion_audit", "*")
    if err:
        errors["agent_memory_promotion_audit"] = err
    report["agent_memory_promotion_audit_total"] = (
        "UNAVAILABLE" if "agent_memory_promotion_audit" in errors else len(promo_audit)
    )

    # ---- 3. is any of it recalled into real turns? ------------------------
    # memoryHitCount is written by assistant_tools when recall returns rows.
    recall: dict[str, Counter] = {}
    turn_actions = (
        "unified_turn.live.completed",
        "unified_turn.live.fallthrough",
        "chat.turn.completed",
    )
    for action in turn_actions:
        offset = 0
        while True:
            try:
                batch = (
                    client.table("audit_events")
                    .select("org_id,action,metadata,created_at")
                    .eq("action", action)
                    .gte("created_at", since)
                    .order("created_at", desc=True)
                    .range(offset, offset + PAGE - 1)
                    .execute()
                )
            except Exception as exc:  # noqa: BLE001
                errors[f"recall:{action}"] = f"{type(exc).__name__}: {exc}"
                break
            data = batch.data or []
            for row in data:
                org = str(row.get("org_id"))
                recall.setdefault(org, Counter())
                recall[org]["turns"] += 1
                meta = _meta(row.get("metadata"))
                hits = _find(meta, "memoryHitCount")
                block = _find(meta, "memory_section")
                if isinstance(hits, int) and hits > 0:
                    recall[org]["memory_hits_present"] += 1
                    recall[org]["memory_hit_rows"] += hits
                elif hits == 0:
                    recall[org]["memory_hits_zero"] += 1
                elif isinstance(block, str) and block.strip():
                    recall[org]["memory_section_nonempty"] += 1
                else:
                    recall[org]["no_memory_signal"] += 1
            if len(data) < PAGE:
                break
            offset += PAGE

    report["recall_by_org"] = {
        org: {
            "org_name": names.get(org, "<unknown>"),
            "is_probe_org": _is_probe(names.get(org, "")),
            **dict(counts),
        }
        for org, counts in sorted(recall.items(), key=lambda kv: -kv[1]["turns"])
    }
    # Is a per-turn memory signal even emitted? Answer this before reporting any
    # recall count, because "0 turns recalled memory" and "no turn records
    # whether memory was recalled" look identical downstream and mean opposite
    # things. unifiedTurnKnowledge counts org_rag/fabric/internet/business_graph
    # hits; memory has no equivalent field, so recall is unmeasurable, not zero.
    signal_totals = Counter()
    for info in report["recall_by_org"].values():
        for key, value in info.items():
            # bool is an int in Python; is_probe_org would otherwise be summed.
            if isinstance(value, int) and not isinstance(value, bool):
                signal_totals[key] += value
    report["turn_memory_signal"] = dict(signal_totals)
    report["memory_recall_is_instrumented"] = bool(
        signal_totals.get("memory_hits_present", 0)
        or signal_totals.get("memory_hits_zero", 0)
        or signal_totals.get("memory_section_nonempty", 0)
    )

    recall_failed = any(key.startswith("recall:") for key in errors)
    report["real_turns_30d"] = (
        "UNAVAILABLE"
        if recall_failed
        else sum(
            info["turns"]
            for info in report["recall_by_org"].values()
            if not info["is_probe_org"]
        )
    )
    if recall_failed:
        report["real_turns_with_memory_recalled"] = "UNAVAILABLE"
    elif not report["memory_recall_is_instrumented"]:
        report["real_turns_with_memory_recalled"] = "NOT INSTRUMENTED"
    else:
        report["real_turns_with_memory_recalled"] = sum(
            info.get("memory_hits_present", 0)
            for info in report["recall_by_org"].values()
            if not info["is_probe_org"]
        )

    report["errors"] = errors
    report["verdict"] = "INCONCLUSIVE — reads failed" if errors else "COMPLETE"
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print("=" * 74)
    print("MEMORY REACH CENSUS  (read-only, 30d)")
    print("=" * 74)
    for line in env_status:
        print(f"  env  {line}")
    print()
    print(f"organizations                          : {report['org_count']}")
    print(f"agent_memories rows (all orgs)         : {report['agent_memories_total']}")
    print(f"agent_memories rows in REAL orgs       : {report['agent_memories_in_real_orgs']}")
    print(f"created range                          : {report['agent_memories_created_range']}")
    print(f"by category                            : {report['agent_memories_by_category']}")
    print(f"by provenance prefix                   : {report['agent_memories_by_provenance_prefix']}")
    print()
    print(f"memory_promotion_candidates            : {report['memory_promotion_candidates_total']}")
    print(f"  by status                            : {report['memory_promotion_candidates_by_status']}")
    print(f"  by org                               : {report['memory_promotion_candidates_by_org']}")
    print(f"agent_memory_promotion_audit rows      : {report['agent_memory_promotion_audit_total']}")
    print()
    print("memories per org:")
    for org, info in report["agent_memories_by_org"].items():
        tag = "PROBE" if info["is_probe_org"] else "real "
        print(f"  [{tag}] {info['org_name']!r:52s} {dict((k, v) for k, v in info.items() if k not in ('org_name', 'is_probe_org'))}")
    print()
    print("turn-level recall (30d):")
    for org, info in report["recall_by_org"].items():
        tag = "PROBE" if info["is_probe_org"] else "real "
        print(f"  [{tag}] {info['org_name']!r:52s}")
        for key, value in info.items():
            if key in ("org_name", "is_probe_org"):
                continue
            print(f"          {key:34s} {value}")
    print()
    print(f"REAL turns 30d                         : {report['real_turns_30d']}")
    print(f"REAL turns with memory recalled        : {report['real_turns_with_memory_recalled']}")
    print(f"memory recall instrumented at all      : {report['memory_recall_is_instrumented']}")
    print(f"per-turn signal tally                  : {report['turn_memory_signal']}")
    print()
    print(f"VERDICT: {report['verdict']}")
    if errors:
        print("  reads that FAILED (these are not zeroes):")
        for key, value in errors.items():
            print(f"    {key:44s} {value}")
    print()
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
