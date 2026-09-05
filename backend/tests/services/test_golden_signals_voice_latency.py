"""Phase 6 (conversational-realism): golden_signals_service voice latency P50/P95/P99.

Real reducer under test (_voice_turn_latency_signals), fed through a fake
Supabase query-builder chain shaped exactly like the real client's
table().select().eq().gte().order().range().execute() calls that
_fetch_rows makes — not a hand-rolled shortcut around the actual function.
"""
from __future__ import annotations

from typing import Any

from app.services import golden_signals_service as mod


class _Result:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class _Query:
    def __init__(self, rows_by_action: dict[str, list[dict]]) -> None:
        self._rows_by_action = rows_by_action
        self._action: str | None = None

    def select(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def eq(self, field: str, value: Any) -> "_Query":
        if field == "action":
            self._action = value
        return self

    def gte(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def order(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def range(self, start: int, end: int) -> "_Query":
        rows = self._rows_by_action.get(self._action or "", [])
        self._range = (start, end)
        return self

    def execute(self) -> _Result:
        rows = self._rows_by_action.get(self._action or "", [])
        start, end = getattr(self, "_range", (0, len(rows)))
        return _Result(rows[start : end + 1])


class FakeClient:
    def __init__(self, rows_by_action: dict[str, list[dict]]) -> None:
        self._rows_by_action = rows_by_action

    def table(self, _name: str) -> _Query:
        return _Query(self._rows_by_action)


def _row(metadata: dict) -> dict:
    return {"action": "x", "created_at": "2026-09-04T00:00:00Z", "metadata": metadata, "resource_id": "r"}


def test_percentiles_computed_independently_per_field_not_correlated_1to1():
    """MUTATION PROOF: llm_stage and e2e rows are two different samples of the
    same turn (not row-joined) — each field's stats must be computed from
    every non-null value it has, independent of the other action's rows.
    """
    llm_rows = [
        _row({"llm_first_token_ms": 100, "llm_first_speakable_chunk_ms": 200, "tts_requested_ms": 210}),
        _row({"llm_first_token_ms": 300, "llm_first_speakable_chunk_ms": 400, "tts_requested_ms": 410}),
    ]
    e2e_rows = [
        _row({"end_to_end_ms": 2000, "user_turn_finalization_ms": 500, "ttfb_by_processor_ms": {"TTS": 150}}),
        _row({"end_to_end_ms": 4000, "user_turn_finalization_ms": 700, "ttfb_by_processor_ms": {"TTS": 180}}),
    ]
    client = FakeClient(
        {
            "voice.turn_latency.llm_stage": llm_rows,
            "voice.turn_latency.e2e": e2e_rows,
        }
    )

    out = mod._voice_turn_latency_signals(client, since_iso="2026-09-01T00:00:00Z", hours=24)

    assert out["llm_first_token"]["sample_count"] == 2
    assert out["llm_first_token"]["p50_ms"] in (100, 300)
    assert out["end_to_end"]["sample_count"] == 2
    assert out["end_to_end"]["max_ms"] == 4000
    assert out["ttfb_by_processor"]["TTS"]["sample_count"] == 2
    assert out["ttfb_by_processor"]["TTS"]["max_ms"] == 180


def test_alert_fires_when_e2e_p50_exceeds_threshold():
    """MUTATION PROOF: the alert threshold comparison must actually read the
    reduced p50/p99, not a hardcoded pass-through.
    """
    e2e_rows = [_row({"end_to_end_ms": 20_000})]
    client = FakeClient({"voice.turn_latency.e2e": e2e_rows, "voice.turn_latency.llm_stage": []})

    out = mod._voice_turn_latency_signals(client, since_iso="2026-09-01T00:00:00Z", hours=24)

    assert any("voice_e2e_p50" in a for a in out["alerts"])
    assert any("voice_e2e_p99" in a for a in out["alerts"])


def test_no_samples_yields_empty_stats_not_an_error():
    client = FakeClient({"voice.turn_latency.e2e": [], "voice.turn_latency.llm_stage": []})
    out = mod._voice_turn_latency_signals(client, since_iso="2026-09-01T00:00:00Z", hours=24)
    assert out["end_to_end"]["sample_count"] == 0
    assert out["end_to_end"]["p50_ms"] is None
    assert out["alerts"] == []
