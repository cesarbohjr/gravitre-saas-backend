"""3.0-B JIT efficiency baseline aggregation."""
from __future__ import annotations

from app.services.jit_efficiency_baseline import (
    aggregate_context_profile_rows,
    aggregate_tool_namespace_rows,
    compare_stage_regression,
    filter_critical_path_jit_cohort,
)
from app.services.jit_efficiency_service import (
    CONTEXT_PROFILE_ACTION,
    TOOL_NAMESPACE_ACTION,
    record_jit_context_profile,
    record_jit_tool_namespace,
)


def test_aggregate_tool_namespace_rows() -> None:
    rows = [
        {
            "metadata": {
                "totalTools": 100,
                "visibleTools": 12,
                "payloadBytes": 4096,
                "narrowMs": 35,
                "retrievalMethod": "embedding_narrow_tools_for_turn",
                "embeddingToolRetrieval": True,
                "eligiblePrefixesApplied": True,
            }
        },
        {
            "metadata": {
                "totalTools": 80,
                "visibleTools": 8,
                "payloadBytes": 2048,
                "narrowMs": 28,
                "retrievalMethod": "keyword_narrow_tools_for_turn",
                "embeddingToolRetrieval": False,
                "spokenChatNoTools": True,
            }
        },
    ]
    out = aggregate_tool_namespace_rows(rows)
    assert out["sample_count"] == 2
    assert out["visible_tools"]["p50_ms"] == 8
    assert out["embedding_turns"] == 1
    assert out["spoken_chat_no_tools_turns"] == 1


def test_aggregate_context_profile_rows() -> None:
    rows = [
        {
            "metadata": {
                "mode": "shadow",
                "tokensUsed": 4000,
                "tokenBudget": 12000,
                "candidateCount": 10,
                "selectedCount": 4,
                "legacyPromptChars": 8000,
                "rankedPromptChars": 6000,
            }
        }
    ]
    out = aggregate_context_profile_rows(rows)
    assert out["sample_count"] == 1
    assert out["shadow_turns"] == 1
    assert out["char_savings_vs_legacy"]["p50_ms"] == 2000


def test_compare_stage_regression_flags_worse_p95() -> None:
    before = {
        "by_stage_delta_ms": {
            "CONTEXT_BUILD": {"p50_ms": 100, "p95_ms": 200, "sample_count": 5},
            "TOOL_DISCOVERY": {"p50_ms": 50, "p95_ms": 80, "sample_count": 5},
        }
    }
    after = {
        "by_stage_delta_ms": {
            "CONTEXT_BUILD": {"p50_ms": 90, "p95_ms": 250, "sample_count": 3},
            "TOOL_DISCOVERY": {"p50_ms": 40, "p95_ms": 70, "sample_count": 3},
        }
    }
    out = compare_stage_regression(before=before, after=after)
    assert out["any_regression"] is True
    assert out["stages"]["CONTEXT_BUILD"]["p95_regressed"] is True
    assert out["stages"]["TOOL_DISCOVERY"]["p95_regressed"] is False


def test_filter_critical_path_jit_cohort_pairs_by_conversation() -> None:
    jit_rows = [
        {
            "resource_id": "conv-a",
            "created_at": "2026-09-19T10:00:00+00:00",
        }
    ]
    critical_rows = [
        {
            "resource_id": "conv-a",
            "created_at": "2026-09-19T10:00:30+00:00",
            "metadata": {"total_ms": 1000},
        },
        {
            "resource_id": "conv-b",
            "created_at": "2026-09-19T10:00:30+00:00",
            "metadata": {"total_ms": 900},
        },
    ]
    matched = filter_critical_path_jit_cohort(critical_rows, jit_rows)
    assert len(matched) == 1
    assert matched[0]["resource_id"] == "conv-a"


def test_record_jit_audits_best_effort_no_raise(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def _fake_write(_client, _org, _user, action, _rtype, _rid, payload):
        calls.append((action, payload))

    monkeypatch.setattr(
        "app.services.jit_efficiency_service._dispatch_background",
        lambda work, _name: work(),
    )
    monkeypatch.setattr(
        "app.workflows.audit.write_audit_event",
        _fake_write,
    )
    monkeypatch.setattr(
        "app.workflows.repository.get_supabase_client",
        lambda _settings: object(),
    )
    settings = object()
    record_jit_tool_namespace(
        settings,
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
        tool_stats={"totalTools": 50, "visibleTools": 10, "retrievalMethod": "keyword"},
        classification={"capability_id": "crm.deals.read"},
        visible_tools=[{"function": {"name": "hubspot_search_deals"}}],
        narrow_ms=20,
        payload_bytes=1024,
    )
    record_jit_context_profile(
        settings,
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
        context_ranking={
            "mode": "shadow",
            "candidateCount": 5,
            "selectedCount": 2,
            "tokensUsed": 1000,
        },
        classification={"capability_id": "crm.deals.read"},
    )
    assert calls[0][0] == TOOL_NAMESPACE_ACTION
    assert calls[0][1]["visibleTools"] == 10
    assert calls[0][1]["eligiblePrefixesApplied"] is True
    assert calls[1][0] == CONTEXT_PROFILE_ACTION
    assert calls[1][1]["mode"] == "shadow"


def test_record_jit_skips_without_user() -> None:
    record_jit_tool_namespace(
        object(),
        org_id="org-1",
        user_id=None,
        conversation_id="conv-1",
        tool_stats={"totalTools": 1, "visibleTools": 1},
    )
