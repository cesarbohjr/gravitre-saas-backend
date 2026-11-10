"""ECO-001: cancellation of the Chat turn must not erase an in-flight write outcome.

This focused runtime regression covers the irreversible-dispatch side of the
boundary. It is NOT the authenticated provider/ledger acceptance certificate.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    _DETACHED_WRITES,
)


@pytest.mark.asyncio
async def test_cancelled_chat_waiter_preserves_inflight_write_until_terminal_result():
    entered = asyncio.Event()
    release = asyncio.Event()
    terminal = asyncio.Event()
    observed = []

    async def provider_execution(**kwargs):
        entered.set()
        await release.wait()
        observed.append("provider_write")
        observed.append("simulated_terminal_callback")
        terminal.set()
        return SimpleNamespace(success=True)

    service = object.__new__(ChatConnectorExecutionService)
    with patch.object(service, "_execute_plan", side_effect=provider_execution):
        waiter = asyncio.create_task(
            service._execute_plan_shielded(plan=SimpleNamespace(kind="write"))
        )
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
            assert observed == [], "Provider was released before cancellation"
            assert len(_DETACHED_WRITES) >= 1, "In-flight write was lost"
        finally:
            release.set()
        await asyncio.wait_for(terminal.wait(), timeout=5)
        await asyncio.sleep(0)
        assert observed == ["provider_write", "simulated_terminal_callback"]
        assert not _DETACHED_WRITES


@pytest.mark.asyncio
async def test_read_only_execution_remains_cancellable():
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def read_execution(**kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    service = object.__new__(ChatConnectorExecutionService)
    with patch.object(service, "_execute_plan", side_effect=read_execution):
        waiter = asyncio.create_task(
            service._execute_plan_shielded(plan=SimpleNamespace(kind="read"))
        )
        await asyncio.wait_for(entered.wait(), timeout=5)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        await asyncio.wait_for(cancelled.wait(), timeout=5)


@pytest.mark.asyncio
async def test_cancelled_chat_waiter_preserves_failed_write_outcome(caplog):
    """A detached provider failure must be observed, not silently discarded."""
    entered = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()

    async def provider_execution(**kwargs):
        entered.set()
        try:
            await release.wait()
            raise RuntimeError("synthetic provider terminal failure")
        finally:
            finished.set()

    service = object.__new__(ChatConnectorExecutionService)
    with patch.object(service, "_execute_plan", side_effect=provider_execution):
        waiter = asyncio.create_task(
            service._execute_plan_shielded(plan=SimpleNamespace(kind="write"))
        )
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
            assert _DETACHED_WRITES, "Failed write must remain tracked after turn cancellation"
        finally:
            release.set()
        await asyncio.wait_for(finished.wait(), timeout=5)
        for _ in range(20):
            if not _DETACHED_WRITES:
                break
            await asyncio.sleep(0)
        assert not _DETACHED_WRITES, "Detached write reference must be cleaned up"
        assert any(
            "detached_write_failed" in record.message
            and "synthetic provider terminal failure" in record.message
            for record in caplog.records
        ), "Terminal provider failure must be observed after turn cancellation"
