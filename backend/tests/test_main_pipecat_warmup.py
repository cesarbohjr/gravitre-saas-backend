"""Mutation-proof tests for the pipecat import-warmup fix (2026-09-06).

Regression this guards against: `pipecat`'s own import is expensive on a cold
worker (confirmed live: a user's first `GET /api/voice/status` after a fresh
deploy took 12,880ms vs ~300ms warm). That cold-import tax used to be paid
inline, inside a live request (`_pipecat_import_available()` /
`_pipecat_available()`), which blew past the frontend's 8s client timeout on
`/api/voice/status` and silently downgraded the whole voice session to the
legacy, less-robust HTTP `<audio>`-element duplex path — the confirmed root
cause of the live "no reply / audio" + "Audio playback failed during voice
reply" report this fix addresses.

`app.main._import_pipecat_stack()` moves that cost to app startup (see
`lifespan()` -> `_warm_pipecat_imports()`), off the request path, in a
background thread, gated on `voice_pipecat_enabled`. These tests exercise the
synchronous, module-level warmup function directly (no event loop / lifespan
needed) so a future refactor cannot silently remove or break it without a
test failure.
"""
from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from unittest.mock import patch

import pytest

from app.main import _import_pipecat_stack, _warm_pipecat_imports


def test_import_pipecat_stack_returns_true_on_clean_import() -> None:
    """When pipecat + our pipeline module import cleanly, report success."""
    fake_pipecat = ModuleType("pipecat")
    fake_pipeline_module = ModuleType("app.services.pipecat_voice.pipeline")
    with patch.dict(
        sys.modules,
        {
            "pipecat": fake_pipecat,
            "app.services.pipecat_voice.pipeline": fake_pipeline_module,
        },
    ):
        assert _import_pipecat_stack() is True


def test_import_pipecat_stack_returns_false_when_pipecat_not_installed() -> None:
    """Missing pipecat package: warmup reports failure, never raises."""
    real_import = __import__

    def _raising_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "pipecat":
            raise ImportError("no pipecat installed")
        return real_import(name, *args, **kwargs)  # type: ignore[misc]

    with patch("builtins.__import__", side_effect=_raising_import):
        assert _import_pipecat_stack() is False


def test_import_pipecat_stack_never_raises_on_pipeline_import_failure() -> None:
    """A broken app.services.pipecat_voice.pipeline import (any exception, not
    just ImportError — e.g. a genuine AttributeError inside a transitive
    pipecat submodule) must be swallowed. Warmup is best-effort observability,
    never something that can crash app startup.
    """
    fake_pipecat = ModuleType("pipecat")
    real_import = __import__

    def _raising_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "app.services.pipecat_voice.pipeline" or (
            args and len(args) >= 3 and args[2] and "pipeline" in args[2]
        ):
            raise RuntimeError("simulated transitive pipecat submodule crash")
        return real_import(name, *args, **kwargs)  # type: ignore[misc]

    with patch.dict(sys.modules, {"pipecat": fake_pipecat}):
        with patch.dict(sys.modules, clear=False):
            sys.modules.pop("app.services.pipecat_voice.pipeline", None)
            with patch("builtins.__import__", side_effect=_raising_import):
                assert _import_pipecat_stack() is False


@pytest.mark.parametrize("enabled", [True, False])
def test_warm_pipecat_imports_gated_on_feature_flag(enabled: bool) -> None:
    """The async lifespan wrapper must only pay the import cost when
    VOICE_PIPECAT_ENABLED is actually on — never unconditionally at startup
    for deployments that don't use Pipecat at all.
    """
    fake_settings = type("FakeSettings", (), {"voice_pipecat_enabled": enabled})()
    with (
        patch("app.config.get_settings", return_value=fake_settings),
        patch("app.main._import_pipecat_stack") as mock_import,
    ):
        asyncio.run(_warm_pipecat_imports())
    if enabled:
        mock_import.assert_called_once()
    else:
        mock_import.assert_not_called()


def test_warm_pipecat_imports_runs_off_the_event_loop_thread() -> None:
    """The blocking import must go through asyncio.to_thread, not run inline
    on the event loop — otherwise a slow/cold import would still stall every
    other coroutine on this worker during startup warmup.
    """
    fake_settings = type("FakeSettings", (), {"voice_pipecat_enabled": True})()
    seen_threads: list[int] = []

    def _record_thread_and_import() -> bool:
        import threading

        seen_threads.append(threading.get_ident())
        return True

    import threading

    main_thread_id = threading.get_ident()
    with (
        patch("app.config.get_settings", return_value=fake_settings),
        patch("app.main._import_pipecat_stack", side_effect=_record_thread_and_import),
    ):
        asyncio.run(_warm_pipecat_imports())

    assert seen_threads, "warmup import was never invoked"
    assert seen_threads[0] != main_thread_id, (
        "pipecat warmup import ran on the event loop thread — a slow/cold "
        "import here would block the whole worker during startup, defeating "
        "the point of warming it off the request path"
    )
