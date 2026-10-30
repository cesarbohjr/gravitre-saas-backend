"""A later turn must not release an old thread's native assignment write."""
import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from app.operators.agent_jobs import create_job
from app.services.tool_types import ToolValidationError
from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation


@pytest.mark.asyncio
async def test_old_cancelled_worker_cannot_insert_after_new_turn_begins():
    client = MagicMock()
    old = TurnCancellation()
    started, release = threading.Event(), threading.Event()

    def worker():
        started.set()
        assert release.wait(5)
        with pytest.raises(ToolValidationError) as blocked:
            create_job(client, 'isolated-org', payload={'task': 'synthetic'})
        return blocked.value.code

    with bound_turn_cancellation(old):
        task = asyncio.create_task(asyncio.to_thread(worker))
    try:
        while not started.is_set():
            await asyncio.sleep(.001)
        old.cancel('user_cancel')
        with bound_turn_cancellation(TurnCancellation()):
            release.set()
            assert await asyncio.wait_for(task, 5) == 'write_commit_interrupted'
    finally:
        release.set()
    client.table.assert_not_called()
