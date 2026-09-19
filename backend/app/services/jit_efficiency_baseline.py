"""3.0-B efficiency baseline aggregation from runtime.jit.* audit events."""
from __future__ import annotations

import json
from typing import Any

from app.services.turn_latency_baseline import (
    aggregate_critical_path_rows,
    parse_audit_metadata,
    percentile,
    stats_ms,
)


TOOL_NAMESPACE_ACTION = "runtime.jit.tool_namespace"
CONTEXT_PROFILE_ACTION = "runtime.jit.context_profile"


def _int_values(rows: list[dict[str, Any]], field: str) -> list[int]:
    values: list[int] = []
    for row in rows:
        meta = parse_audit_metadata(row)
        raw = meta.get(field)
        if isinstance(raw, (int, float)):
            values.append(int(raw))
    return values


def aggregate_tool_namespace_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_tools = _int_values(rows, "totalTools")
    visible_tools = _int_values(rows, "visibleTools")
    payload_bytes = _int_values(rows, "payloadBytes")
    narrow_ms = _int_values(rows, "narrowMs")
    embedding_on = 0
    eligible_on = 0
    spoken_no_tools = 0
    methods: dict[str, int] = {}
    for row in rows:
        meta = parse_audit_metadata(row)
        method = str(meta.get("retrievalMethod") or "unknown")
        methods[method] = methods.get(method, 0) + 1
        if meta.get("embeddingToolRetrieval") is True:
            embedding_on += 1
        if meta.get("eligiblePrefixesApplied") is True:
            eligible_on += 1
        if meta.get("spokenChatNoTools") is True:
            spoken_no_tools += 1
    compression_ratios: list[int] = []
    for row in rows:
        meta = parse_audit_metadata(row)
        total = meta.get("totalTools")
        visible = meta.get("visibleTools")
        if isinstance(total, (int, float)) and isinstance(visible, (int, float)) and total:
            compression_ratios.append(int(round((float(visible) / float(total)) * 100)))
    ratio_stats = stats_ms(compression_ratios) if compression_ratios else {}
    if ratio_stats:
        ratio_stats = {**ratio_stats, "unit": "visible_pct_of_total"}
    return {
        "sample_count": len(rows),
        "retrieval_methods": methods,
        "embedding_turns": embedding_on,
        "eligible_prefix_turns": eligible_on,
        "spoken_chat_no_tools_turns": spoken_no_tools,
        "total_tools": stats_ms(total_tools),
        "visible_tools": stats_ms(visible_tools),
        "payload_bytes": stats_ms(payload_bytes),
        "narrow_ms": stats_ms(narrow_ms),
        "visible_pct_of_total": ratio_stats,
    }


def aggregate_context_profile_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tokens_used = _int_values(rows, "tokensUsed")
    token_budget = _int_values(rows, "tokenBudget")
    candidate_count = _int_values(rows, "candidateCount")
    selected_count = _int_values(rows, "selectedCount")
    legacy_chars = _int_values(rows, "legacyPromptChars")
    ranked_chars = _int_values(rows, "rankedPromptChars")
    shadow = 0
    active = 0
    char_savings: list[int] = []
    for row in rows:
        meta = parse_audit_metadata(row)
        mode = str(meta.get("mode") or "")
        if mode == "shadow":
            shadow += 1
        elif mode == "active":
            active += 1
        legacy = meta.get("legacyPromptChars")
        ranked = meta.get("rankedPromptChars")
        if isinstance(legacy, (int, float)) and isinstance(ranked, (int, float)):
            char_savings.append(max(0, int(legacy) - int(ranked)))
    return {
        "sample_count": len(rows),
        "shadow_turns": shadow,
        "active_turns": active,
        "tokens_used": stats_ms(tokens_used),
        "token_budget": stats_ms(token_budget),
        "candidate_count": stats_ms(candidate_count),
        "selected_count": stats_ms(selected_count),
        "legacy_prompt_chars": stats_ms(legacy_chars),
        "ranked_prompt_chars": stats_ms(ranked_chars),
        "char_savings_vs_legacy": stats_ms(char_savings),
    }


def compare_stage_regression(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    stages: tuple[str, ...] = ("CONTEXT_BUILD", "TOOL_DISCOVERY"),
) -> dict[str, Any]:
    """Compare p50/p95 stage deltas; flag regression when after > before."""
    before_stages = (before.get("by_stage_delta_ms") or {}) if isinstance(before, dict) else {}
    after_stages = (after.get("by_stage_delta_ms") or {}) if isinstance(after, dict) else {}
    comparisons: dict[str, Any] = {}
    any_regression = False
    for stage in stages:
        b = before_stages.get(stage) or {}
        a = after_stages.get(stage) or {}
        b_p50 = b.get("p50_ms")
        b_p95 = b.get("p95_ms")
        a_p50 = a.get("p50_ms")
        a_p95 = a.get("p95_ms")
        p50_regressed = (
            isinstance(b_p50, int)
            and isinstance(a_p50, int)
            and a_p50 > b_p50
        )
        p95_regressed = (
            isinstance(b_p95, int)
            and isinstance(a_p95, int)
            and a_p95 > b_p95
        )
        if p50_regressed or p95_regressed:
            any_regression = True
        comparisons[stage] = {
            "before_p50_ms": b_p50,
            "before_p95_ms": b_p95,
            "after_p50_ms": a_p50,
            "after_p95_ms": a_p95,
            "p50_regressed": p50_regressed,
            "p95_regressed": p95_regressed,
            "before_sample_count": b.get("sample_count"),
            "after_sample_count": a.get("sample_count"),
        }
    return {"stages": comparisons, "any_regression": any_regression}


def load_baseline_snapshot(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
