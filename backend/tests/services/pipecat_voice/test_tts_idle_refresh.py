"""TtsIdleRefresher wires tts_idle_should_refresh: reconnect a dead idle socket, leave a live one."""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import Settings
from app.services.pipecat_voice import pipeline as pipeline_module
from app.services.pipecat_voice.tts_warmup import TtsIdleRefresher, tts_socket_open


class _FakeTTS:
    def __init__(self, state: str | None) -> None:
        self._websocket = SimpleNamespace(state=SimpleNamespace(name=state)) if state else None
        self.calls: list[str] = []

    async def _disconnect(self) -> None:
        self.calls.append("disconnect")
        self._websocket = None

    async def _connect(self) -> None:
        self.calls.append("connect")
        self._websocket = SimpleNamespace(state=SimpleNamespace(name="OPEN"))


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _refresher(tts: Any, clock: _Clock, *, busy: bool = False, last: float | None = None) -> TtsIdleRefresher:
    return TtsIdleRefresher(
        tts, last_activity=lambda: last, busy=lambda: busy, idle_expiry_s=45, clock=clock
    )


def test_socket_open_detection() -> None:
    assert tts_socket_open(_FakeTTS("OPEN"))
    assert not tts_socket_open(_FakeTTS("CLOSED"))
    assert not tts_socket_open(_FakeTTS(None))


@pytest.mark.asyncio
async def test_dead_socket_is_rebuilt_only_after_the_idle_expiry() -> None:
    clock = _Clock()
    tts = _FakeTTS("CLOSED")
    refresher = _refresher(tts, clock)
    clock.t += 10
    assert await refresher.tick() is None
    assert tts.calls == []
    clock.t += 40  # 50 s idle
    result = await refresher.tick()
    assert result is not None and result["ok"] is True
    # Full teardown first so the service recreates its receive task.
    assert tts.calls == ["disconnect", "connect"]
    assert refresher.refreshes == 1
    # The refresh restarts the idle window.
    clock.t += 5
    assert await refresher.tick() is None


@pytest.mark.asyncio
async def test_open_socket_is_left_to_the_keepalive() -> None:
    clock = _Clock()
    tts = _FakeTTS("OPEN")
    refresher = _refresher(tts, clock)
    clock.t += 60
    assert await refresher.tick() is None
    assert tts.calls == []


@pytest.mark.asyncio
async def test_never_refreshes_while_speaking_or_generating() -> None:
    clock = _Clock()
    tts = _FakeTTS("CLOSED")
    refresher = _refresher(tts, clock, busy=True)
    clock.t += 120
    assert await refresher.tick() is None
    assert tts.calls == []


@pytest.mark.asyncio
async def test_recent_audio_activity_postpones_the_refresh() -> None:
    clock = _Clock()
    tts = _FakeTTS("CLOSED")
    clock.t += 100
    refresher = TtsIdleRefresher(
        tts, last_activity=lambda: clock.t - 10, busy=lambda: False, idle_expiry_s=45, clock=clock
    )
    clock.t += 1
    assert await refresher.tick() is None


def test_flag_defaults_off_and_pipeline_gates_the_refresher_on_it() -> None:
    assert Settings.model_fields["voice_tts_idle_refresh_v1"].default is False
    source = inspect.getsource(pipeline_module.build_pipecat_voice_task)
    assert 'getattr(settings, "voice_tts_idle_refresh_v1", False)' in source
    assert "if idle_refresh_enabled and not idle_refresh_tasks" in source
