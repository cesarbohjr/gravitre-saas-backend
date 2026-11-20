"""P27-08: worker-only OS kill/restart cannot terminate the API process."""
from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace

import pytest


def test_api_worker_start_disabled_in_process_when_child_is_selected(monkeypatch):
    from app.workers import workflow_worker
    settings = SimpleNamespace(
        workflow_queue_enabled=True,
        workflow_worker_process_isolation_enabled=True,
        workflow_queue_poll_seconds=5,
    )
    monkeypatch.setattr(workflow_worker, "get_settings", lambda: settings)
    assert workflow_worker.start_workflow_run_worker() is None


def test_isolation_default_is_disabled():
    from app.config import Settings
    settings = Settings(
        _env_file=None, APP_ENV="test",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_ANON_KEY="test",
        SUPABASE_SERVICE_ROLE_KEY="test",
        SUPABASE_JWT_SECRET="test",
    )
    assert settings.workflow_worker_process_isolation_enabled is False


@pytest.mark.asyncio
async def test_worker_os_kill_restarts_child_while_parent_http_server_remains_live():
    from app.workers.isolated_workflow_supervisor import (
        supervise_workflow_worker, stop_isolated_workflow_worker,
    )

    async def handle(reader, writer):
        await reader.read(4096)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    launched = []
    # Real OS child, no connections or external providers: the supervisor's
    # production spawn/wait/restart mechanism is exercised without service risk.
    cmd = (
        sys.executable, "-u", "-c",
        "import time; time.sleep(120)",
    )
    task = asyncio.create_task(supervise_workflow_worker(
        command=cmd, restart_delay=1.0,
        on_started=lambda child: launched.append(child),
    ))

    async def api_ok():
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(4096), 5)
        writer.close()
        await writer.wait_closed()
        assert b"200 OK" in response and response.endswith(b"OK")

    try:
        async def until_size(n):
            for _ in range(100):
                if len(launched) >= n:
                    return
                await asyncio.sleep(.1)
            raise AssertionError("worker subprocess not started or restarted")

        await until_size(1)
        first = launched[0]
        assert first.pid != os.getpid() and first.returncode is None
        await api_ok()
        first.kill()  # SIGKILL this child only, never the parent HTTP process
        assert await first.wait() != 0
        await until_size(2)
        second = launched[1]
        assert second.pid != first.pid and second.returncode is None
        await api_ok()
        assert not task.done()
    finally:
        await stop_isolated_workflow_worker(task)
        server.close()
        await server.wait_closed()
    assert second.returncode is not None


@pytest.mark.asyncio
async def test_api_shutdown_terminates_only_the_isolated_child():
    from app.workers.isolated_workflow_supervisor import (
        supervise_workflow_worker, stop_isolated_workflow_worker,
    )
    launched = []
    task = asyncio.create_task(supervise_workflow_worker(
        command=(sys.executable, "-u", "-c", "import time; time.sleep(120)"),
        restart_delay=1.0,
        on_started=lambda child: launched.append(child)))
    try:
        for _ in range(100):
            if launched:
                break
            await asyncio.sleep(.1)
        assert launched and launched[0].returncode is None
    finally:
        await stop_isolated_workflow_worker(task)
    assert launched[0].returncode is not None
    assert task.done()
