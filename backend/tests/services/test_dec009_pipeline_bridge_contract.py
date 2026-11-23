"""DEC-009 source contracts; database/analytics I/O is isolated, not acceptance."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import unified_turn_pipeline_bridge as bridge
from app.services.performance_dashboard_service import _build_pipeline_waterfall, _latency_stats
from app.services.speculative_execution import SpeculativeScope, speculative_scope


@pytest.fixture
def sink(monkeypatch):
    from app.services import clickhouse_service, latency_tracking

    rows = []
    db = MagicMock()
    db.table.return_value.insert.side_effect = lambda row: (
        rows.append(row) or SimpleNamespace(execute=lambda: SimpleNamespace(data=[]))
    )
    replica = SimpleNamespace(insert_events=AsyncMock())
    monkeypatch.setattr(latency_tracking, "get_supabase_client", lambda _settings: db)
    monkeypatch.setattr(clickhouse_service, "get_clickhouse_service", lambda: replica)
    return SimpleNamespace(rows=rows, db=db, replica=replica)


def _breakdown():
    return {
        "registry_tools_ms": 10, "narrow_tools_ms": 20,
        "embed_query_ms": 30, "context_prompt_ms": 40,
        "openai_create_schedule_ms": 50, "model_ttft_ms": 60,
        "pre_first_token_overhead_ms": 70, "model_total_ms": 80,
        "wall_to_first_token_ms": 90,
        # These producer fields must not become arbitrary database columns.
        "inference_provider": "synthetic-provider", "prompt_tokens": 123,
        "completion_tokens": 45, "error": "SECRET_SENTINEL",
        "messages": "PRIVATE_SENTINEL", "unknown_stage_ms": 999,
    }


def _track_emission(monkeypatch):
    loop = asyncio.get_running_loop()
    tasks = []

    def create_task(coro):
        task = loop.create_task(coro)
        tasks.append(task)
        return task

    # Replace only the bridge's module reference, not global asyncio functions.
    monkeypatch.setattr(bridge, "asyncio", SimpleNamespace(
        get_running_loop=lambda: SimpleNamespace(create_task=create_task),
    ))
    return tasks


@pytest.mark.asyncio
async def test_actual_producer_bridge_writer_and_waterfall_preserve_stage_identity(monkeypatch, sink):
    from app.services.unified_turn_reasoning_service import _log_unified_turn_breakdown

    tasks = _track_emission(monkeypatch)
    _log_unified_turn_breakdown(
        "org-a", _breakdown(), outcome="ok", model="synthetic-model",
        settings=SimpleNamespace(), message_id="message-a",
    )
    await asyncio.gather(*tasks)
    await asyncio.sleep(0)  # Drain isolated analytics coroutines.
    expected = {
        "unified_registry_tools": 10, "unified_narrow_tools": 20,
        "unified_embed_query": 30, "unified_context_prompt": 40,
        "unified_openai_schedule": 50, "unified_model_ttft": 60,
        "unified_pre_token_overhead": 70, "unified_model_total": 80,
        "unified_wall_ttft": 90,
    }
    assert {r["stage_name"]: r["duration_ms"] for r in sink.rows} == expected
    assert len(sink.rows) == 9
    for row in sink.rows:
        assert row["org_id"] == "org-a"
        assert row["message_id"] == "message-a"
        assert row["model_used"] == "synthetic-model"
        assert set(row) == {
            "id", "org_id", "message_id", "stage_name", "duration_ms", "cache_hit", "model_used",
        }
        assert "PRIVATE_SENTINEL" not in str(row)
        assert "SECRET_SENTINEL" not in str(row)
    assert sink.db.table.call_args_list[0].args == ("ai_pipeline_latency",)
    assert sink.replica.insert_events.await_count == 9
    for call in sink.replica.insert_events.await_args_list:
        table, rows = call.args
        assert table == "gravitre.pipeline_events"
        assert rows[0]["org_id"] == "org-a"
        assert rows[0]["message_id"] == "message-a"
        assert rows[0]["model_used"] == "synthetic-model"
    stats = {r["stage_name"]: _latency_stats([r["duration_ms"]]) for r in sink.rows}
    waterfall = _build_pipeline_waterfall(stats)
    assert {r["stage"]: r["avgMs"] for r in waterfall["unifiedTurn"]} == expected
    assert waterfall["classical"] == []
    assert waterfall["hasUnifiedTurnData"] is True
    assert waterfall["hasClassicalData"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [None, "25", -1, float("nan"), float("inf"), {}, []])
async def test_bad_stage_does_not_erase_later_valid_stage_or_wall(monkeypatch, sink, invalid):
    tasks = _track_emission(monkeypatch)
    bridge.bridge_unified_turn_breakdown_to_pipeline(
        SimpleNamespace(), org_id="org-a",
        breakdown={"registry_tools_ms": invalid, "model_total_ms": 80, "wall_to_first_token_ms": 90},
    )
    await asyncio.gather(*tasks)
    assert [(r["stage_name"], r["duration_ms"]) for r in sink.rows] == [
        ("unified_model_total", 80), ("unified_wall_ttft", 90),
    ]


@pytest.mark.parametrize("org_id,breakdown", [("", {"model_total_ms": 5}), ("org-a", {})])
def test_empty_identity_or_breakdown_emits_nothing(sink, org_id, breakdown):
    bridge.bridge_unified_turn_breakdown_to_pipeline(
        SimpleNamespace(), org_id=org_id, breakdown=breakdown,
    )
    assert sink.rows == []
    sink.db.table.assert_not_called()


def test_sync_bridge_uses_real_writer_without_event_loop(sink):
    bridge.bridge_unified_turn_breakdown_to_pipeline(
        SimpleNamespace(), org_id="org-b", breakdown={"model_total_ms": 0},
    )
    assert len(sink.rows) == 1
    assert sink.rows[0]["duration_ms"] == 0
    assert sink.rows[0]["message_id"] is None
    assert sink.rows[0]["org_id"] == "org-b"


@pytest.mark.asyncio
async def test_persistence_failure_does_not_abort_later_stage(monkeypatch, sink):
    from app.services import latency_tracking

    original = latency_tracking.log_pipeline_latency

    async def fail_first(settings, **kwargs):
        if kwargs["stage_name"] == "unified_registry_tools":
            raise RuntimeError("synthetic telemetry outage")
        await original(settings, **kwargs)

    monkeypatch.setattr(latency_tracking, "log_pipeline_latency", fail_first)
    tasks = _track_emission(monkeypatch)
    bridge.bridge_unified_turn_breakdown_to_pipeline(
        SimpleNamespace(), org_id="org-a",
        breakdown={"registry_tools_ms": 10, "model_total_ms": 80},
    )
    await asyncio.gather(*tasks)
    assert [(r["stage_name"], r["duration_ms"]) for r in sink.rows] == [("unified_model_total", 80)]


@pytest.mark.asyncio
@pytest.mark.parametrize("adopt", [False, True])
async def test_speculative_bridge_has_no_durable_write_until_adoption(monkeypatch, sink, adopt):
    tasks = _track_emission(monkeypatch)
    scope = SpeculativeScope()
    with speculative_scope(scope):
        bridge.bridge_unified_turn_breakdown_to_pipeline(
            SimpleNamespace(), org_id="org-a", breakdown={"model_total_ms": 80},
        )
        await asyncio.gather(*tasks)
        assert sink.rows == []
        sink.replica.insert_events.assert_not_awaited()
        assert scope.deferred_labels == ["latency.pipeline"]
        if adopt:
            await scope.commit()
        else:
            scope.discard()
    await asyncio.sleep(0)
    assert len(sink.rows) == int(adopt)
    assert sink.replica.insert_events.await_count == int(adopt)
