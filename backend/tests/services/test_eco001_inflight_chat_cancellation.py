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
        observed.append("terminal_outcome_persisted")
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
        assert observed == ["provider_write", "terminal_outcome_persisted"]
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
