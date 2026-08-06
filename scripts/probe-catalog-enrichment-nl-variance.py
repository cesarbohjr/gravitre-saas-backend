#!/usr/bin/env python3
"""Catalog-scale NL-variance + latency probe for enriched semantic retrieval.

Hard targets (Part 3):
  - correct-tool selection ≥90% on ≥200 cases spanning all vendors
  - withhold_no_tool battery still 100%
  - embed/narrow latency not regressed vs Prompt-1 Phase 4 gate band

Writes docs/delivery/catalog-enrichment-nl-variance-live.json
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "docs" / "delivery" / "catalog-enrichment-nl-variance-live.json"

# Prompt-1 Phase 4 standing band (task battery wall p50 ~973; narrow should stay low).
NARROW_ALERT_MS = int(os.environ.get("ENRICH_NARROW_ALERT_MS", "200"))
EMBED_QUERY_ALERT_MS = int(os.environ.get("ENRICH_EMBED_QUERY_ALERT_MS", "150"))
CORRECT_TARGET = float(os.environ.get("ENRICH_CORRECT_TARGET", "0.90"))
MIN_CASES = int(os.environ.get("ENRICH_MIN_CASES", "200"))


def _load_dotenv() -> None:
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    for p in (BACKEND / ".env.operator.local", BACKEND / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in dotenv_values(p, encoding=enc).items():
                    if v and k not in os.environ:
                        os.environ[k] = v
                break
            except UnicodeDecodeError:
                continue


def _tool_invoke(tool: dict[str, Any]) -> str:
    inv = str(tool.get("invoke_action") or "").strip().lower()
    if inv:
        return inv
    fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
    name = str(fn.get("name") or tool.get("name") or "")
    from app.connectors.action_catalog.action_id_resolve import (
        resolve_action_id_from_tool_name,
    )

    return resolve_action_id_from_tool_name(name)


def _visible_invokes(tools: list[dict[str, Any]]) -> list[str]:
    return [_tool_invoke(t) for t in tools]


def _expected_in_visible(expected: str, visible: list[str]) -> bool:
    exp = expected.lower()
    if exp in visible:
        return True
    # allow underscore form
    und = exp.replace(".", "_")
    for v in visible:
        if v == exp or v.replace(".", "_") == und or und in v.replace(".", "_"):
            return True
        if exp.split(".")[-1] and v.endswith(exp.split(".")[-1]) and exp.split(".")[0] in v:
            return True
    return False


def build_cases() -> list[dict[str, Any]]:
    """≥200 cases: enrichment examples + systematic variants across all vendors."""
    from app.connectors.action_catalog.action_retrieval_enrichment import (
        enrichment_catalog,
        enrichment_for_action,
    )
    from app.connectors.action_catalog.registry import all_catalog_action_specs, get_vendor_catalog

    # Ensure enrichment on for case building
    import app.connectors.action_catalog.action_retrieval_enrichment as enrich_mod

    enrich_mod.ENRICHMENT_ENABLED = True
    enrich_mod.clear_enrichment_cache()

    specs = list(all_catalog_action_specs())
    by_vendor: dict[str, list[Any]] = defaultdict(list)
    for s in specs:
        by_vendor[s.id.split(".", 1)[0]].append(s)

    # Priority wrong-tool classes + broad coverage
    priority_vendors = [
        "github",
        "clickup",
        "salesforce",
        "monday",
        "hubspot",
        "apollo",
        "gmail",
        "slack",
        "asana",
        "notion",
        "linear",
        "zendesk",
        "intercom",
        "airtable",
        "jira",
        "stripe",
    ]
    vendors = list(get_vendor_catalog().keys())
    ordered = [v for v in priority_vendors if v in by_vendor] + [
        v for v in sorted(vendors) if v not in priority_vendors and v in by_vendor
    ]

    cases: list[dict[str, Any]] = []
    # Round-robin sample actions per vendor until ≥MIN_CASES with 5–8 phrasings each
    per_vendor_actions = 2  # 77*2=154 actions * ~5 examples ≈ 770; we'll cap
    for vendor in ordered:
        pool = by_vendor[vendor]
        # Prefer search/list/create verbs
        ranked = sorted(
            pool,
            key=lambda s: (
                0
                if any(x in s.id for x in (".search", ".list", ".create", ".send", ".get"))
                else 1,
                s.id,
            ),
        )
        for spec in ranked[:per_vendor_actions]:
            row = enrichment_for_action(spec.id) or enrichment_catalog().get(spec.id.lower()) or {}
            examples = list(row.get("examples") or [])
            # Ensure 5–8 variants
            while len(examples) < 5:
                examples.append(f"{spec.name} via {vendor}")
            examples = examples[:8]
            for i, msg in enumerate(examples):
                cases.append(
                    {
                        "id": f"{spec.id}#{i}",
                        "vendor": vendor,
                        "expected": spec.id,
                        "message": msg,
                        "kind": spec.kind,
                    }
                )
            if len(cases) >= max(MIN_CASES, 200) and vendor not in priority_vendors[:4]:
                # keep going until all vendors represented at least once
                pass

    # Guarantee every vendor appears at least once
    seen_vendors = {c["vendor"] for c in cases}
    for vendor in ordered:
        if vendor in seen_vendors:
            continue
        spec = by_vendor[vendor][0]
        row = enrichment_for_action(spec.id) or {}
        msg = (row.get("examples") or [f"use {vendor} {spec.name}"])[0]
        cases.append(
            {
                "id": f"{spec.id}#0",
                "vendor": vendor,
                "expected": spec.id,
                "message": msg,
                "kind": spec.kind,
            }
        )
        seen_vendors.add(vendor)

    if len(cases) < MIN_CASES:
        # add more actions from large vendors
        for vendor in ordered:
            for spec in by_vendor[vendor][per_vendor_actions : per_vendor_actions + 3]:
                row = enrichment_for_action(spec.id) or {}
                for i, msg in enumerate(list(row.get("examples") or [spec.name])[:5]):
                    cases.append(
                        {
                            "id": f"{spec.id}#{i}",
                            "vendor": vendor,
                            "expected": spec.id,
                            "message": msg,
                            "kind": spec.kind,
                        }
                    )
                if len(cases) >= MIN_CASES:
                    break
            if len(cases) >= MIN_CASES:
                break

    return cases


def run_retrieval_probe(cases: list[dict[str, Any]]) -> dict[str, Any]:
    from app.config import get_settings
    from app.connectors.action_catalog import action_retrieval_enrichment as enrich_mod
    from app.services.tool_registry import get_tool_registry
    from app.services.unified_turn_tool_retrieval import (
        embed_narrow_tools_for_turn,
        warm_tool_document_embeddings,
    )

    enrich_mod.ENRICHMENT_ENABLED = True
    enrich_mod.clear_enrichment_cache()
    settings = get_settings()
    warm_n = warm_tool_document_embeddings(settings=settings)

    # Broad connected set so catalog tools are available
    vendors = sorted({c["vendor"] for c in cases})
    connected = vendors + ["platform"]
    reg = get_tool_registry()
    tools = list(reg.get_tools_for_agent(["*"], connected))

    rows: list[dict[str, Any]] = []
    narrow_ms: list[int] = []
    embed_ms: list[int] = []
    top1 = 0
    topk = 0

    for case in cases:
        t0 = time.perf_counter()
        visible, stats = embed_narrow_tools_for_turn(
            tools,
            query=case["message"],
            settings=settings,
            org_id="enrich-nl-probe",
            connected_integrations=[case["vendor"], "platform"],
            classification={"requires_action": True},
            requires_action=True,
            max_tools=16,
        )
        wall = int((time.perf_counter() - t0) * 1000)
        invs = _visible_invokes(list(visible))
        hit = _expected_in_visible(case["expected"], invs)
        rank = None
        exp = case["expected"].lower()
        for idx, inv in enumerate(invs):
            if inv == exp or exp.replace(".", "_") in inv.replace(".", "_"):
                rank = idx
                break
        if hit:
            topk += 1
        if rank == 0:
            top1 += 1
        n_ms = int(stats.get("narrow_tools_ms") or stats.get("embed_narrow_total_ms") or wall)
        e_ms = int(stats.get("embed_query_ms") or stats.get("embed_query_encode_ms") or 0)
        narrow_ms.append(n_ms)
        if e_ms:
            embed_ms.append(e_ms)
        rows.append(
            {
                **case,
                "hit_topk": hit,
                "rank": rank,
                "top1": rank == 0,
                "narrow_tools_ms": n_ms,
                "embed_query_ms": e_ms or None,
                "retrieval_method": stats.get("retrievalMethod"),
                "visible_sample": invs[:5],
            }
        )

    n = len(rows)
    correct_rate = round(topk / max(1, n), 4)
    top1_rate = round(top1 / max(1, n), 4)
    return {
        "warm_tool_docs": warm_n,
        "tool_pool_size": len(tools),
        "n": n,
        "vendors_covered": len(vendors),
        "correct_topk_rate": correct_rate,
        "correct_top1_rate": top1_rate,
        "correct_topk_n": topk,
        "correct_top1_n": top1,
        "narrow_tools_ms_p50": int(statistics.median(narrow_ms)) if narrow_ms else None,
        "narrow_tools_ms_max": max(narrow_ms) if narrow_ms else None,
        "embed_query_ms_p50": int(statistics.median(embed_ms)) if embed_ms else None,
        "embed_query_ms_max": max(embed_ms) if embed_ms else None,
        "target_correct_rate": CORRECT_TARGET,
        "meets_correct_target": correct_rate >= CORRECT_TARGET,
        "latency_ok": (
            (not narrow_ms or statistics.median(narrow_ms) <= NARROW_ALERT_MS)
            and (not embed_ms or statistics.median(embed_ms) <= EMBED_QUERY_ALERT_MS)
        ),
        "misses_sample": [r for r in rows if not r["hit_topk"]][:40],
        "rows": rows,
    }


def run_withhold() -> dict[str, Any]:
    """Run the standing withhold battery tests with enrichment ON."""
    from app.connectors.action_catalog import action_retrieval_enrichment as enrich_mod
    from tests.services import test_routing_nl_variance_battery as battery

    enrich_mod.ENRICHMENT_ENABLED = True
    results: dict[str, bool] = {}
    errors: dict[str, str] = {}
    for name, fn in (
        ("ambiguous_enrich", battery.test_withhold_fabrication_on_ambiguous_enrich),
        (
            "no_matching_action_connected_vendor",
            battery.test_withhold_no_matching_action_connected_vendor,
        ),
        (
            "advise_only_mentions_vendor",
            battery.test_withhold_explicit_advise_only_mentions_vendor,
        ),
    ):
        try:
            fn()
            results[name] = True
        except AssertionError as exc:
            results[name] = False
            errors[name] = str(exc)[:240]
    passed = sum(1 for v in results.values() if v)
    return {
        "categories": results,
        "errors": errors,
        "pass_n": passed,
        "pass_rate": passed / 3.0,
        "meets_100pct": passed == 3,
    }


def ab_enrichment_delta(cases: list[dict[str, Any]], *, sample: int = 80) -> dict[str, Any]:
    """Compare enrichment ON vs OFF on a sample (mirrors original 18-action delta)."""
    from app.config import get_settings
    from app.connectors.action_catalog import action_retrieval_enrichment as enrich_mod
    from app.services.tool_registry import get_tool_registry
    from app.services.unified_turn_tool_retrieval import embed_narrow_tools_for_turn

    settings = get_settings()
    sample_cases = cases[:sample]
    vendors = sorted({c["vendor"] for c in sample_cases})
    tools = list(get_tool_registry().get_tools_for_agent(["*"], vendors + ["platform"]))

    def score(enabled: bool) -> int:
        enrich_mod.ENRICHMENT_ENABLED = enabled
        enrich_mod.clear_enrichment_cache()
        # clear tool embed cache so docs rebuild
        from app.services import unified_turn_tool_retrieval as utr

        with utr._CACHE_LOCK:
            utr._TOOL_EMBED_CACHE.clear()
        hits = 0
        for case in sample_cases:
            visible, _ = embed_narrow_tools_for_turn(
                tools,
                query=case["message"],
                settings=settings,
                org_id="enrich-ab",
                connected_integrations=[case["vendor"], "platform"],
                requires_action=True,
                max_tools=16,
            )
            if _expected_in_visible(case["expected"], _visible_invokes(list(visible))):
                hits += 1
        return hits

    off = score(False)
    on = score(True)
    enrich_mod.ENRICHMENT_ENABLED = True
    return {
        "sample_n": len(sample_cases),
        "correct_enrichment_off": off,
        "correct_enrichment_on": on,
        "delta_correct": on - off,
        "rate_off": round(off / max(1, len(sample_cases)), 4),
        "rate_on": round(on / max(1, len(sample_cases)), 4),
    }


def main() -> int:
    _load_dotenv()
    import httpx

    try:
        health = httpx.get(
            os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/") + "/health",
            timeout=30,
        ).json()
    except Exception:
        health = {}

    from app.connectors.action_catalog.action_retrieval_enrichment import enrichment_coverage

    coverage = enrichment_coverage()
    cases = build_cases()
    retrieval = run_retrieval_probe(cases)
    withhold = run_withhold()
    ab = ab_enrichment_delta(cases, sample=min(80, len(cases)))

    recommend_default_on = bool(
        retrieval.get("meets_correct_target")
        and withhold.get("meets_100pct")
        and retrieval.get("latency_ok")
        and ab.get("delta_correct", 0) >= 0
    )

    report = {
        "feature": "catalog_enrichment_nl_variance",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "api_git_sha": health.get("git_sha"),
        "coverage": coverage,
        "targets": {
            "correct_rate": CORRECT_TARGET,
            "min_cases": MIN_CASES,
            "withhold_100pct": True,
            "narrow_p50_ms_max": NARROW_ALERT_MS,
            "embed_query_p50_ms_max": EMBED_QUERY_ALERT_MS,
        },
        "case_count": len(cases),
        "vendors_in_cases": len({c["vendor"] for c in cases}),
        "retrieval": {
            k: v for k, v in retrieval.items() if k not in {"rows", "misses_sample"}
        },
        "retrieval_misses_sample": retrieval.get("misses_sample"),
        "withhold": withhold,
        "ab_vs_pilot_style": ab,
        "pilot_reference": {
            "sample_actions": 18,
            "delta_correct": 0,
            "note": "Prior G.5 Phase 4.2 mapper probe; this report is embedding retrieval at catalog scale",
        },
        "recommendation": (
            "adopt_enrichment_default_on"
            if recommend_default_on
            else "keep_measuring_or_decline"
        ),
        "verdict": {
            "correct_target": retrieval.get("meets_correct_target"),
            "withhold_ok": withhold.get("meets_100pct"),
            "latency_ok": retrieval.get("latency_ok"),
            "full_coverage": coverage.get("full_coverage"),
            "overall_pass": recommend_default_on and coverage.get("full_coverage"),
        },
    }
    # Keep full rows optional via env
    if os.environ.get("ENRICH_PROBE_INCLUDE_ROWS", "").lower() in {"1", "true"}:
        report["retrieval_rows"] = retrieval.get("rows")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT),
                "case_count": report["case_count"],
                "vendors": report["vendors_in_cases"],
                "correct_topk_rate": retrieval.get("correct_topk_rate"),
                "meets_90": retrieval.get("meets_correct_target"),
                "withhold": withhold.get("meets_100pct"),
                "latency_ok": retrieval.get("latency_ok"),
                "delta_correct": ab.get("delta_correct"),
                "recommendation": report["recommendation"],
                "overall_pass": report["verdict"]["overall_pass"],
            },
            indent=2,
        )
    )
    return 0 if report["verdict"]["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
