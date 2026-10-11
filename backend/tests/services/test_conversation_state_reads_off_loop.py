"""task_state reads and read-modify-writes both leave the event loop.

The read-modify-write runs on one worker thread under a per-conversation
lock, so nothing can interleave between its read and its write.
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from app.services.conversation_state_service import ConversationStateService


class _Query:
    def __init__(self, db: "_Db", op: str, payload=None) -> None:
        self.db, self.op, self.payload = db, op, payload

    def select(self, *_a, **_k):
        return self

    def update(self, payload):
        return _Query(self.db, "update", payload)

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        self.db.threads.append((self.op, threading.current_thread()))
        if self.op == "update":
            self.db.state = self.payload["task_state"]
            return SimpleNamespace(data=[{}])
        return SimpleNamespace(data=[{"task_state": self.db.state}])


class _Db:
    def __init__(self) -> None:
        self.state = {"clarified_params": {"a": 1}}
        self.threads: list[tuple[str, threading.Thread]] = []

    def table(self, _name):
        return _Query(self, "select")


@pytest.mark.asyncio
async def test_plain_read_runs_off_the_event_loop(mock_settings):
    db = _Db()
    state = await ConversationStateService(mock_settings).get_task_state("c1", "o1", client=db)
    assert state["clarified_params"] == {"a": 1}
    assert db.threads[0][0] == "select"
    assert db.threads[0][1] is not threading.current_thread()


@pytest.mark.asyncio
async def test_merge_reads_and_writes_off_the_loop_on_one_thread(mock_settings):
    db = _Db()
    svc = ConversationStateService(mock_settings)
    await svc.update_task_state("c1", "o1", {"clarified_params": {"b": 2}}, client=db)
    loop_thread = threading.current_thread()
    assert [op for op, _ in db.threads] == ["select", "update"]
    (_, read_thread), (_, write_thread) = db.threads
    assert read_thread is write_thread
    assert read_thread is not loop_thread
    assert db.state["clarified_params"] == {"a": 1, "b": 2}
    await svc.get_task_state("c1", "o1", client=db)
    assert db.threads[-1][1] is not loop_thread
