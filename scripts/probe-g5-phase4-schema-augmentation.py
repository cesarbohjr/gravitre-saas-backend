#!/usr/bin/env python3
"""G.5 Phase 4.1–4.3 closeout probe — embedding re-test, enrichment, compression.

Writes docs/delivery/g5-phase4-schema-augmentation-probe.json

Comparable to:
  docs/delivery/unified-turn-embed-latency-fix-2026-07-24.md
  docs/delivery/unified-turn-embed-query-local-fix-2026-07-24.md
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

OUT = ROOT / "docs" / "delivery" / "g5-phase4-schema-augmentation-probe.json"


def _load_dotenv() -> None:
    """Load backend .env into process env without printing values."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                for k, v in loaded.items():
                    if v and k not in os.environ:
                        os.environ[k] = v
                break
            except UnicodeDecodeError:
                continue

EMAIL_INTENT = "Send an email to Stephanie about the proposal"
EMAIL_EXPECT_SUBSTR = ("gmail", "email", "messages_send", "messages.send")

G1_PROBES = [
    ("asana", ["asana"], "create a task in Asana called Follow up with Acme", "asana.tasks.create"),
    ("clickup", ["clickup"], "list my open ClickUp tasks", "clickup.tasks.list"),
    ("github", ["github"], "search GitHub issues mentioning billing", "github.issues.list"),
    ("notion", ["notion"], "create a Notion page titled Q3 plan", "notion.pages.create"),
    ("airtable", ["airtable"], "find records in Airtable for Acme", "airtable.records.list"),
    ("monday", ["monday"], "create a Monday.com item for onboarding", "monday.items.create"),
    ("linear", ["linear"], "create a Linear issue titled Fix login", "linear.issues.create"),
    ("zendesk", ["zendesk"], "list open Zendesk tickets", "zendesk.tickets.list"),
    ("salesforce", ["salesforce"], "find Salesforce contacts named Sarah", "salesforce.contacts.search"),
    ("intercom", ["intercom"], "search Intercom conversations about refund", "intercom.conversations.search"),
]

# NL-variance / withhold probes used for compression accuracy (Phase 3 battery shape).
WITHHOLD_PROBES = [
    ("ambiguous_enrich", "enrich my list with Clay and sync somewhere", "clarify"),
    (
        "github_wiki_no_tool",
        "update the GitHub wiki page about onboarding",
        "no_wrong_tool",
    ),
    (
        "advise_only",
        "should I use HubSpot or Salesforce for this deal — just advise, don't run anything",
        "no_tool",
    ),
]


def _estimate_tokens(obj: Any) -> int:
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    # ~4 chars/token heuristic used across prior delivery probes.
    return max(1, len(raw) // 4)


def _payload_bytes(obj: Any) -> int:
    return len(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _load_tools(*, target_size: int = 70) -> list[dict[str, Any]]:
    """Load OpenAI tool defs; trim to ~70 to match original email_intent A/B class."""
    from app.services.tool_registry import get_tool_registry

    connected = [
        "gmail",
        "hubspot",
        "apollo",
        "slack",
        "clay",
        "github",
        "salesforce",
        "asana",
        "clickup",
        "notion",
        "airtable",
        "monday",
        "linear",
        "zendesk",
        "intercom",
        "platform",
    ]
    reg = get_tool_registry()
    tools = list(reg.get_tools_for_agent(["*"], connected))
    if len(tools) > target_size:
        priority = []
        rest = []
        for t in tools:
            fn = t.get("function") if isinstance(t.get("function"), dict) else {}
            name = str(fn.get("name") or t.get("name") or "").lower()
            inv = str(t.get("invoke_action") or "").lower()
            integ = str(t.get("integration") or "").lower()
            if any(
                x in name or x in inv or x in integ
                for x in ("gmail", "email", "platform", "assistant")
            ):
                priority.append(t)
            else:
                rest.append(t)
        tools = (priority + rest)[:target_size]
    return tools


def _tool_names(tools: list[dict[str, Any]]) -> list[str]:
    out = []
    for t in tools:
        fn = t.get("function") if isinstance(t.get("function"), dict) else {}
        out.append(str(fn.get("name") or t.get("name") or ""))
    return out


def _email_hit(tools: list[dict[str, Any]]) -> bool:
    blob = " ".join(_tool_names(tools)).lower()
    inv = " ".join(str(t.get("invoke_action") or "") for t in tools).lower()
    combined = blob + " " + inv
    return any(s in combined for s in EMAIL_EXPECT_SUBSTR)


def _shadow_settings(*, embed: bool, base: Any) -> Any:
    """Clone settings-like object forcing embed on/off for A/B."""
    from types import SimpleNamespace

    d = {
        "unified_turn_shadow_enabled": True,
        "unified_turn_live_enabled": False,
        "unified_turn_shadow_max_tools": 32,
        "unified_turn_task_max_tools": 16,
        "unified_turn_task_model_tier": "",
        "unified_turn_embedding_tool_retrieval": True,
        "unified_turn_embed_min_catalog_tools": 40 if embed else 9999,
        "unified_turn_tool_embed_local": True,
        "unified_turn_tool_embed_model": getattr(base, "unified_turn_tool_embed_model", None)
        or "all-MiniLM-L6-v2",
        "unified_turn_tool_query_cache_ttl_sec": 300,
        "unified_turn_progressive_schemas": True,
        "openai_api_key": getattr(base, "openai_api_key", None) or os.environ.get("OPENAI_API_KEY"),
        "unified_turn_qa_hooks_enabled": False,
    }
    # Force keyword by disabling embedding flag when embed=False (cleaner than huge min).
    if not embed:
        d["unified_turn_embedding_tool_retrieval"] = False
    return SimpleNamespace(**d)


def _run_shadow_ab(tools: list[dict[str, Any]], settings: Any) -> dict[str, Any]:
    """Real OpenAI shadow A/B for email_intent — yields model_ttft_ms + wall."""
    import asyncio
    from unittest.mock import patch

    from app.services.unified_turn_reasoning_service import run_unified_turn_shadow

    async def _one(*, embed: bool) -> dict[str, Any]:
        s = _shadow_settings(embed=embed, base=settings)
        if not (s.openai_api_key or "").strip():
            return {"error": "openai_not_configured"}
        with patch(
            "app.services.unified_turn_reasoning_service.get_tool_registry"
        ) as reg:
            mock_reg = reg.return_value
            mock_reg.get_tools_for_agent.return_value = list(tools)
            wall0 = time.perf_counter()
            result = await run_unified_turn_shadow(
                org_id="probe-g5-p41",
                user_id="probe-user",
                conversation_id=None,
                message=EMAIL_INTENT,
                task_state={},
                conversation_history=[],
                connected_integrations=["gmail", "hubspot", "apollo", "slack"],
                settings=s,  # type: ignore[arg-type]
            )
            wall_ms = int((time.perf_counter() - wall0) * 1000)
        bd = dict(result.latency_breakdown or {})
        return {
            "outcome_kind": result.outcome_kind,
            "error": result.error,
            "narrow_tools_ms": bd.get("narrow_tools_ms"),
            "model_ttft_ms": bd.get("model_ttft_ms"),
            "wall_ms": wall_ms,
            "pre_model_ms": bd.get("pre_model_ms"),
            "tools_payload_bytes": bd.get("tools_payload_bytes"),
            "embedding_tool_retrieval": bd.get("embedding_tool_retrieval"),
            "retrieval_method": bd.get("retrieval_method"),
            "embed_query_ms": bd.get("embed_query_ms"),
            "embed_query_method": bd.get("embed_query_method"),
            "visible_tools": bd.get("visible_tools"),
            "progressive_disclosure": bd.get("progressive_disclosure"),
        }

    async def _both() -> dict[str, Any]:
        # Keyword first, then embed (warm docs already from narrow-only path).
        kw = await _one(embed=False)
        emb = await _one(embed=True)
        return {"keyword_shadow": kw, "embedding_shadow": emb}

    try:
        return asyncio.run(_both())
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:400]}


def phase41_embedding_vs_keyword(tools: list[dict[str, Any]]) -> dict[str, Any]:
    from app.config import get_settings
    from app.services.agent_platform_optimizer import narrow_tools_for_turn
    from app.services.unified_turn_tool_retrieval import embed_narrow_tools_for_turn

    settings = get_settings()
    connected = ["gmail", "hubspot", "apollo", "slack"]
    classification = {"requires_action": True}

    # Warm local embed path once so timing matches post-warm investigation.
    try:
        from app.services.unified_turn_tool_retrieval import warm_tool_document_embeddings

        warm_n = warm_tool_document_embeddings(settings=settings)
    except Exception as exc:  # noqa: BLE001
        warm_n = -1
        warm_err = str(exc)[:200]
    else:
        warm_err = None

    # Keyword path
    t0 = time.perf_counter()
    kw_tools, kw_stats = narrow_tools_for_turn(
        tools,
        query=EMAIL_INTENT,
        classification=classification,
        connected_integrations=connected,
        requires_action=True,
        max_tools=32,
    )
    kw_ms = int((time.perf_counter() - t0) * 1000)

    # Embedding path (local SentenceTransformer when available)
    t1 = time.perf_counter()
    emb_tools, emb_stats = embed_narrow_tools_for_turn(
        tools,
        query=EMAIL_INTENT,
        settings=settings,
        org_id="probe-g5-p41",
        connected_integrations=connected,
        classification=classification,
        requires_action=True,
        max_tools=32,
    )
    emb_wall_ms = int((time.perf_counter() - t1) * 1000)
    emb_narrow_ms = int(emb_stats.get("embed_narrow_total_ms") or emb_wall_ms)

    # Second embed call = warm cache (comparable to prod post-warm).
    t2 = time.perf_counter()
    emb2_tools, emb2_stats = embed_narrow_tools_for_turn(
        tools,
        query=EMAIL_INTENT,
        settings=settings,
        org_id="probe-g5-p41",
        connected_integrations=connected,
        classification=classification,
        requires_action=True,
        max_tools=32,
    )
    emb2_wall_ms = int((time.perf_counter() - t2) * 1000)
    emb2_narrow_ms = int(emb2_stats.get("embed_narrow_total_ms") or emb2_wall_ms)

    kw_payload = _payload_bytes(kw_tools)
    emb_payload = _payload_bytes(emb2_tools)

    shadow_ab = _run_shadow_ab(tools, settings)

    kw_narrow = int(kw_stats.get("narrow_tools_ms") or kw_ms)
    emb_method = emb2_stats.get("retrievalMethod")
    fell_back = emb_method == "keyword_narrow_tools_for_turn"

    # Prefer shadow wall/ttft when available for threshold decision.
    sh_kw = (shadow_ab or {}).get("keyword_shadow") or {}
    sh_emb = (shadow_ab or {}).get("embedding_shadow") or {}
    if sh_kw.get("wall_ms") is not None and sh_emb.get("wall_ms") is not None:
        kw_wall = int(sh_kw["wall_ms"])
        emb_wall = int(sh_emb["wall_ms"])
        if fell_back:
            recommendation = "embed_fell_back_to_keyword"
            threshold_note = (
                "Embedding path fell back to keyword — do not change threshold until "
                "local embed path is healthy."
            )
        elif emb_wall + 80 < kw_wall and sh_emb.get("embedding_tool_retrieval"):
            recommendation = "keep_embed_min_40"
            threshold_note = (
                f"Post-Phase-4 when/why: embedding wall {emb_wall}ms beats keyword "
                f"{kw_wall}ms on email_intent @ {len(tools)} tools — KEEP "
                "UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=40."
            )
        elif kw_wall + 80 < emb_wall:
            recommendation = "raise_embed_min_toward_200"
            threshold_note = (
                f"Post-Phase-4 when/why: keyword wall {kw_wall}ms beats embedding "
                f"{emb_wall}ms — propose raising UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS."
            )
        else:
            recommendation = "keep_embed_min_40"
            threshold_note = (
                f"Post-Phase-4 when/why: walls within 80ms (kw={kw_wall}, emb={emb_wall}); "
                "KEEP UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=40 (no evidence to raise)."
            )
    elif fell_back:
        recommendation = "embed_fell_back_to_keyword"
        threshold_note = (
            "Embedding path fell back to keyword — do not change threshold until "
            "local embed path is healthy."
        )
    elif emb2_narrow_ms <= max(30, kw_narrow + 25) and _email_hit(emb2_tools):
        recommendation = "keep_embed_min_40"
        threshold_note = (
            "Post-Phase-4 when/why schemas: warm local embed narrow_tools_ms remains "
            "at/under keyword + small epsilon; KEEP UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=40 "
            "(no raise back to 200). Shadow TTFT unavailable in this run."
        )
    elif emb2_narrow_ms > kw_narrow + 100:
        recommendation = "raise_embed_min_toward_200"
        threshold_note = (
            "Warm embed loses on narrow_tools_ms by >100ms vs keyword at ~70-tool class."
        )
    else:
        recommendation = "keep_embed_min_40"
        threshold_note = "Inconclusive wall delta; keep current default 40."

    return {
        "probe": "email_intent",
        "catalog_size_class": len(tools),
        "when_why_context": "post_phase4_f8_100pct_descriptions",
        "warm_tool_docs": warm_n,
        "warm_error": warm_err,
        "keyword": {
            "narrow_tools_ms": kw_narrow,
            "model_ttft_ms": sh_kw.get("model_ttft_ms"),
            "wall_ms": sh_kw.get("wall_ms"),
            "wall_ms_proxy": kw_narrow,
            "payload_bytes": kw_payload,
            "visible": len(kw_tools),
            "email_tool_in_top_k": _email_hit(kw_tools),
            "top_tools": _tool_names(kw_tools)[:8],
            "stats": {k: kw_stats.get(k) for k in ("retrievalMethod", "visibleTools", "totalTools")},
        },
        "embedding_cold": {
            "narrow_tools_ms": emb_narrow_ms,
            "wall_ms_proxy": emb_wall_ms,
            "embed_query_ms": emb_stats.get("embed_query_ms"),
            "embed_query_method": emb_stats.get("embed_query_method")
            or emb_stats.get("embed_query_provider"),
            "payload_bytes": _payload_bytes(emb_tools),
            "email_tool_in_top_k": _email_hit(emb_tools),
            "top_tools": _tool_names(emb_tools)[:8],
            "retrievalMethod": emb_stats.get("retrievalMethod"),
            "fallback": emb_stats.get("embeddingFallbackReason"),
        },
        "embedding_warm": {
            "narrow_tools_ms": emb2_narrow_ms,
            "model_ttft_ms": sh_emb.get("model_ttft_ms"),
            "wall_ms": sh_emb.get("wall_ms"),
            "wall_ms_proxy": emb2_wall_ms,
            "embed_query_ms": emb2_stats.get("embed_query_ms"),
            "embed_query_method": emb2_stats.get("embed_query_method")
            or emb2_stats.get("embed_query_provider"),
            "payload_bytes": emb_payload,
            "email_tool_in_top_k": _email_hit(emb2_tools),
            "top_tools": _tool_names(emb2_tools)[:8],
            "retrievalMethod": emb2_stats.get("retrievalMethod"),
            "cache_hits": emb2_stats.get("embed_tool_doc_cache_hits"),
            "cache_misses": emb2_stats.get("embed_tool_doc_cache_misses"),
        },
        "shadow_ab_comparable": shadow_ab,
        "comparable_table": {
            "format": "matches unified-turn-embed-query-local-fix-2026-07-24.md",
            "keyword": {
                "narrow_tools_ms": sh_kw.get("narrow_tools_ms", kw_narrow),
                "model_ttft_ms": sh_kw.get("model_ttft_ms"),
                "wall_ms": sh_kw.get("wall_ms"),
                "payload_bytes": sh_kw.get("tools_payload_bytes", kw_payload),
            },
            "embedding_local_warm": {
                "narrow_tools_ms": sh_emb.get("narrow_tools_ms", emb2_narrow_ms),
                "model_ttft_ms": sh_emb.get("model_ttft_ms"),
                "wall_ms": sh_emb.get("wall_ms"),
                "payload_bytes": sh_emb.get("tools_payload_bytes", emb_payload),
                "embed_query_ms": sh_emb.get("embed_query_ms") or emb2_stats.get("embed_query_ms"),
            },
        },
        "historical_reference": {
            "keyword_wall_ms": 840,
            "embedding_remote_wall_ms": 1269,
            "embedding_local_wall_ms": 487,
            "embedding_local_narrow_ms": 24,
            "keyword_narrow_ms": 1,
            "source": "unified-turn-embed-query-local-fix-2026-07-24.md",
        },
        "threshold_recommendation": recommendation,
        "threshold_note": threshold_note,
        "current_default_embed_min": int(
            getattr(settings, "unified_turn_embed_min_catalog_tools", 40) or 40
        ),
    }


def phase42_enrichment() -> dict[str, Any]:
    from app.connectors.action_catalog import action_retrieval_enrichment as enrich_mod
    from app.connectors.action_catalog.action_retrieval_enrichment import (
        ACTION_RETRIEVAL_ENRICHMENT,
    )
    from app.services.chat_action_mapper import ChatActionMapper

    mapper = ChatActionMapper()

    def run_g1(*, enabled: bool) -> list[dict[str, Any]]:
        enrich_mod.ENRICHMENT_ENABLED = enabled
        rows = []
        for vendor, conns, msg, expected in G1_PROBES:
            match = mapper.match_segment(msg, connected_integrations=conns)
            hit = match is not None
            tool = match.entry.registry_key if match else None
            score = round(float(match.score), 2) if match else None
            correct = bool(tool and (tool == expected or expected.split(".")[-1] in (tool or "")))
            # Accept sibling resource hits only if expected verb family matches loosely.
            if hit and not correct and tool:
                # Exact expected is the success criterion for this probe.
                correct = tool == expected
            rows.append(
                {
                    "vendor": vendor,
                    "message": msg,
                    "expected": expected,
                    "hit": hit,
                    "tool": tool,
                    "score": score,
                    "correct": correct,
                }
            )
        return rows

    baseline = run_g1(enabled=False)
    enriched = run_g1(enabled=True)
    enrich_mod.ENRICHMENT_ENABLED = True  # restore

    def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "hits": sum(1 for r in rows if r["hit"]),
            "correct": sum(1 for r in rows if r["correct"]),
            "n": len(rows),
            "rows": rows,
        }

    b = summary(baseline)
    e = summary(enriched)
    delta_correct = e["correct"] - b["correct"]
    if delta_correct >= 2:
        rec = "adopt_catalog_wide_rollout"
        effort = "M (2–4 eng-days): extend builder to emit examples/tags for all ~689; CI lint; mapper+embed already wired"
    elif delta_correct == 1:
        rec = "defer_sample_only"
        effort = "S — keep sample enrichment; revisit after more wrong-tool incidents"
    else:
        rec = "decline_catalog_wide"
        effort = "none — sample kept for documentation; no catalog-wide maintenance burden"

    return {
        "sample_action_count": len(ACTION_RETRIEVAL_ENRICHMENT),
        "sample_actions": sorted(ACTION_RETRIEVAL_ENRICHMENT.keys()),
        "baseline_no_enrichment": b,
        "with_enrichment": e,
        "delta_correct": delta_correct,
        "recommendation": rec,
        "effort_estimate": effort,
    }


def phase43_compression(tools: list[dict[str, Any]]) -> dict[str, Any]:
    from app.services.agent_platform_optimizer import (
        compress_tool_definitions,
        compress_tool_definitions_aggressive,
        narrow_tools_for_turn,
    )
    from app.services.progressive_tool_schemas import apply_progressive_disclosure
    from app.services.chat_action_mapper import ChatActionMapper
    from app.services.pack_common_intent_defaults import (
        try_pack_common_list_create_plan,
        try_pack_common_msp_enrich_workflow_plan,
    )
    from app.services.retrieve_plan_gate import retrieve_plan_or_none
    from app.connectors.action_catalog import action_retrieval_enrichment as enrich_mod

    connected = ["gmail", "hubspot", "apollo", "slack", "clay"]
    narrowed, stats = narrow_tools_for_turn(
        tools,
        query=EMAIL_INTENT,
        classification={"requires_action": True},
        connected_integrations=connected,
        requires_action=True,
        max_tools=32,
    )
    # Current compress already applied inside narrow_tools_for_turn.
    current = list(narrowed)
    aggressive = compress_tool_definitions_aggressive(current)
    # Uncompressed-ish: re-narrow then skip? Use raw tools filtered by names.
    names = set(_tool_names(current))
    raw = []
    for t in tools:
        fn = t.get("function") if isinstance(t.get("function"), dict) else {}
        if str(fn.get("name") or t.get("name") or "") in names:
            raw.append(t)

    progressive, _, _ = apply_progressive_disclosure(current)

    token_table = {
        "raw_narrowed_no_extra_compress": {
            "tokens_est": _estimate_tokens(raw),
            "bytes": _payload_bytes(raw),
            "n": len(raw),
        },
        "current_compress": {
            "tokens_est": _estimate_tokens(current),
            "bytes": _payload_bytes(current),
            "n": len(current),
        },
        "aggressive_compress_preserve_when_why": {
            "tokens_est": _estimate_tokens(aggressive),
            "bytes": _payload_bytes(aggressive),
            "n": len(aggressive),
        },
        "progressive_stubs_plus_search": {
            "tokens_est": _estimate_tokens(list(progressive)),
            "bytes": _payload_bytes(list(progressive)),
            "n": len(list(progressive)),
        },
    }

    cur_tok = token_table["current_compress"]["tokens_est"]
    agg_tok = token_table["aggressive_compress_preserve_when_why"]["tokens_est"]
    prog_tok = token_table["progressive_stubs_plus_search"]["tokens_est"]
    savings_vs_current_pct = round(100.0 * (cur_tok - agg_tok) / max(1, cur_tok), 1)
    # Marginal value once progressive already shipped.
    savings_vs_progressive_pct = round(
        100.0 * (prog_tok - min(agg_tok, prog_tok)) / max(1, prog_tok), 1
    )

    # Accuracy: Phase 3 withhold / NL battery (mapper path — schemas not in loop).
    # Enrichment stays OFF (catalog-wide declined); battery must pass on shipping path.
    enrich_mod.ENRICHMENT_ENABLED = False
    mapper = ChatActionMapper()
    CONNECTED = ["apollo", "hubspot", "clay", "slack", "gmail"]

    c1 = [
        'Use Clay to enrich the existing Apollo contact list "MSP Prospects", then add those enriched contacts to the existing HubSpot static list "MSPs".',
        "enrich my apollo MSP Prospects list with Clay and sync to HubSpot MSPs",
        "Clay enrich Apollo list MSP Prospects into HubSpot list MSPs",
        "please take MSP Prospects from Apollo, enrich via Clay, put them on HubSpot MSPs",
        "run clay enrichment on the apollo msp prospects list and push to hubspot",
        "I need clay to enrich contacts then hubspot sync for msp prospects",
        "enrich contacts with clay then add to hubspot",
    ]
    c2 = [
        "Create a HubSpot static list named MSPs",
        "make me a new hubspot list called MSPs",
        "add a contact list MSPs in hubspot",
        "new apollo contact list for msp outreach",
        "can you set up a list MSPs on hubspot?",
        "I want a hubspot segment named MSPs",
        "create list",
        "spin up an outreach list in apollo for MSPs",
    ]
    c1_hits = sum(
        1
        for m in c1
        if try_pack_common_msp_enrich_workflow_plan(m, connected_integrations=CONNECTED)
    )
    c2_hits = sum(
        1
        for m in c2
        if try_pack_common_list_create_plan(m, connected_integrations=CONNECTED)
    )

    # Withhold checks (same assertions as CI battery shape).
    withhold = {}
    retrieved = retrieve_plan_or_none(
        "enrich my list with Clay and sync somewhere",
        org_id="org",
        connected_integrations=CONNECTED,
        client=None,
        require_pack_install=False,
    )
    withhold["cat1_ambiguous_clarify"] = bool(
        retrieved and retrieved.kind == "clarify" and retrieved.block_fabrication
    )
    gh = mapper.match_segment(
        "update the GitHub wiki page about onboarding",
        connected_integrations=["github"],
    )
    withhold["cat2_no_wrong_github_wiki"] = gh is None or (
        "wiki" not in (gh.entry.registry_key or "")
        and "pages" not in (gh.entry.registry_key or "")
    )
    advise_msg = (
        "Don't take any action and don't call any tools — just advise me on whether "
        "HubSpot lists or Apollo lists are better for MSP outreach."
    )
    advise = mapper.match_segment(advise_msg, connected_integrations=CONNECTED)
    pack_msp = try_pack_common_msp_enrich_workflow_plan(
        advise_msg, connected_integrations=CONNECTED
    )
    pack_list = try_pack_common_list_create_plan(
        advise_msg, connected_integrations=CONNECTED
    )
    withhold["cat3_advise_only_no_tool"] = (
        advise is None and pack_msp is None and pack_list is None
    )

    # When/why cue retention after aggressive compress.
    cue_words = ("when ", "use this", "use to", "prefer ", "for when")
    before_cues = 0
    after_cues = 0
    for a, b in zip(current, aggressive):
        da = str((a.get("function") or {}).get("description") or "").lower()
        db = str((b.get("function") or {}).get("description") or "").lower()
        if any(c in da for c in cue_words):
            before_cues += 1
        if any(c in db for c in cue_words):
            after_cues += 1

    # Recommendation: aggressive only worth it if material vs current AND not
    # redundant with progressive stubs (which already dominate token cut).
    if savings_vs_current_pct >= 15 and prog_tok > agg_tok * 1.5:
        # Unusual: progressive somehow larger — adopt aggressive as standing.
        rec = "adopt_aggressive_as_standing_step"
    elif savings_vs_current_pct >= 15 and prog_tok < cur_tok * 0.5:
        # Progressive already cut most; aggressive on full schemas helps search-load path only.
        rec = "adopt_for_full_schema_load_path_only"
    elif savings_vs_current_pct < 8:
        rec = "decline_redundant_with_progressive"
    else:
        rec = "defer_optional_full_schema_load_compress"

    return {
        "narrowed_visible": len(current),
        "narrow_stats": {k: stats.get(k) for k in ("totalTools", "visibleTools", "retrievalMethod")},
        "token_table": token_table,
        "savings_aggressive_vs_current_pct": savings_vs_current_pct,
        "progressive_already_smaller_than_current": prog_tok < cur_tok,
        "when_why_cues_in_narrowed": {"before": before_cues, "after_aggressive": after_cues},
        "nl_battery": {
            "c1_msp_hits": c1_hits,
            "c1_n": len(c1),
            "c2_list_hits": c2_hits,
            "c2_n": len(c2),
            "withhold": withhold,
            "note": (
                "Mapper/pack batteries do not consume OpenAI tool schemas; "
                "accuracy here confirms compression does not regress NL routing. "
                "Schema token effect is the primary compression metric."
            ),
        },
        "recommendation": rec,
        "recommendation_note": (
            "Phase 2 progressive stubs already reduce attach payload far below "
            f"current compressed full schemas ({prog_tok} vs {cur_tok} est tokens). "
            f"Aggressive extra cut on full schemas is {savings_vs_current_pct}% vs current — "
            "relevant mainly when search_catalog_tools loads full defs, not for stub attach."
        ),
    }


def main() -> int:
    _load_dotenv()
    try:
        from app.config import get_settings

        get_settings.cache_clear()
    except Exception:  # noqa: BLE001
        pass
    tools = _load_tools(target_size=70)
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha_local": _git_sha(),
        "catalog_tools_loaded": len(tools),
        "phase_4_1_embedding_vs_keyword": phase41_embedding_vs_keyword(tools),
        "phase_4_2_enrichment": phase42_enrichment(),
        "phase_4_3_compression": phase43_compression(tools),
    }
    # Final dispositions
    p41 = report["phase_4_1_embedding_vs_keyword"]
    p42 = report["phase_4_2_enrichment"]
    p43 = report["phase_4_3_compression"]
    report["dispositions"] = {
        "4.1_embedding_retest": {
            "status": "CLOSED",
            "decision": p41["threshold_recommendation"],
            "evidence": "g5-phase4-schema-augmentation-probe.json#phase_4_1",
        },
        "4.2_enriched_fields": {
            "status": "CLOSED",
            "decision": p42["recommendation"],
            "delta_correct": p42["delta_correct"],
            "evidence": "g5-phase4-schema-augmentation-probe.json#phase_4_2",
        },
        "4.3_schema_compression": {
            "status": "CLOSED",
            "decision": p43["recommendation"],
            "savings_pct": p43["savings_aggressive_vs_current_pct"],
            "evidence": "g5-phase4-schema-augmentation-probe.json#phase_4_3",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["dispositions"], indent=2))
    print("wrote", OUT)
    return 0


def _git_sha() -> str:
    try:
        import subprocess

        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short=12", "HEAD"],
                cwd=str(ROOT),
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:  # noqa: BLE001
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
