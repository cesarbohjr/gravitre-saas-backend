"""The dedicated I/O pool must be larger than the default executor and sizable."""
from __future__ import annotations

import asyncio
import threading

import pytest

import app.core.io_pool as io_pool


@pytest.fixture(autouse=True)
def _reset_pool():
    original = io_pool._POOL
    io_pool._POOL = None
    yield
    if io_pool._POOL is not None and io_pool._POOL is not original:
        io_pool._POOL.shutdown(wait=False)
    io_pool._POOL = original


class TestSizing:
    def test_default_width(self) -> None:
        # Deliberately the same width as the default executor on the deploy target
        # (cpu_count=48 -> min(32, 52) = 32). This pool is for isolation from
        # other to_thread callers, not for extra capacity; an earlier rationale
        # claiming the default was ~6 workers was disproved in production.
        assert io_pool._DEFAULT_SIZE == 32
        assert io_pool.get_io_pool()._max_workers == 32

    def test_size_is_env_tunable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IO_THREAD_POOL_SIZE", "48")
        assert io_pool.get_io_pool()._max_workers == 48

    def test_junk_env_falls_back_to_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IO_THREAD_POOL_SIZE", "not-a-number")
        assert io_pool.get_io_pool()._max_workers == 32

    def test_zero_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("IO_THREAD_POOL_SIZE", "0")
        assert io_pool.get_io_pool()._max_workers == 32

    def test_pool_is_reused(self) -> None:
        assert io_pool.get_io_pool() is io_pool.get_io_pool()


class TestOffloadSwitch:
    def test_defaults_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VOICE_CONTEXT_IO_OFFLOAD", raising=False)
        assert io_pool.offload_enabled() is True

    @pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "off", " off "])
    def test_falsey_values_disable(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("VOICE_CONTEXT_IO_OFFLOAD", value)
        assert io_pool.offload_enabled() is False

    @pytest.mark.parametrize("value", ["true", "1", "yes", "anything-else"])
    def test_other_values_keep_it_on(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("VOICE_CONTEXT_IO_OFFLOAD", value)
        assert io_pool.offload_enabled() is True

    @pytest.mark.asyncio
    async def test_disabled_runs_inline_on_the_loop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VOICE_CONTEXT_IO_OFFLOAD", "false")
        here = threading.get_ident()
        assert await io_pool.run_io(threading.get_ident) == here

    @pytest.mark.asyncio
    async def test_disabled_still_forwards_args_and_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VOICE_CONTEXT_IO_OFFLOAD", "false")
        assert await io_pool.run_io(lambda a, *, b: (a, b), 1, b=2) == (1, 2)

        def _boom():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await io_pool.run_io(_boom)


class TestRunIo:
    @pytest.mark.asyncio
    async def test_runs_off_the_calling_thread(self) -> None:
        here = threading.get_ident()
        where = await io_pool.run_io(threading.get_ident)
        assert where != here

    @pytest.mark.asyncio
    async def test_forwards_args_and_kwargs(self) -> None:
        def _f(a, b, *, c):
            return (a, b, c)

        assert await io_pool.run_io(_f, 1, 2, c=3) == (1, 2, 3)

    @pytest.mark.asyncio
    async def test_propagates_exceptions(self) -> None:
        def _boom():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await io_pool.run_io(_boom)

    @pytest.mark.asyncio
    async def test_does_not_use_the_default_executor(self) -> None:
        # A blocked default executor must not stall these reads, which is what
        # made retrieval_gather queue behind other to_thread callers.
        names: list[str] = []

        def _name() -> str:
            return threading.current_thread().name

        names.append(await io_pool.run_io(_name))
        names.append(await asyncio.to_thread(_name))
        assert names[0].startswith("gravitre-io")
        assert not names[1].startswith("gravitre-io")

    @pytest.mark.asyncio
    async def test_concurrency_exceeds_the_default_executor_width(self) -> None:
        # Ten simultaneous blocking reads must not serialize into ~6 slots.
        started = asyncio.Event()
        gate = threading.Event()
        live = 0
        peak = 0
        lock = threading.Lock()

        def _hold() -> None:
            nonlocal live, peak
            with lock:
                live += 1
                peak = max(peak, live)
            gate.wait(timeout=5)
            with lock:
                live -= 1

        async def _watch() -> None:
            await asyncio.sleep(0.2)
            started.set()
            gate.set()

        await asyncio.gather(
            *[io_pool.run_io(_hold) for _ in range(10)],
            _watch(),
        )
        assert started.is_set()
        assert peak >= 10, f"only {peak} blocking reads ran concurrently"
