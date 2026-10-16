"""In-process provider harness: one logical operation → one side effect (with mocked ledger claim)."""
from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.tool_types import NormalizedResult, ToolContext
from app.services.write_invoke_idempotency import WriteClaimResult


class _FakeProvider:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls = 0

    def invoke(self) -> NormalizedResult:
        with self.lock:
            self.calls += 1
        return NormalizedResult(success=True, action="hubspot.contacts.update", data={"id": "1"})


def _run_with_claim(claim_results: list[WriteClaimResult], provider: _FakeProvider) -> NormalizedResult | None:
    """Simulates invoke spine: claim → provider or replay."""
    claim = claim_results.pop(0)
    if claim.outcome == "replay" and claim.replay:
        return claim.replay
    if claim.outcome == "blocked":
        return None
    if claim.outcome == "claimed":
        return provider.invoke()
    return None


def test_concurrent_logical_operation_one_provider_call():
    provider = _FakeProvider()
    claim_queue = [WriteClaimResult(outcome="claimed")] + [
        WriteClaimResult(outcome="blocked", status="in_progress")
    ] * 7
    lock = threading.Lock()
    results: list[NormalizedResult | None] = []

    def worker():
        with lock:
            if not claim_queue:
                return
            c = claim_queue.pop(0)
        results.append(_run_with_claim([c], provider))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert provider.calls == 1
    assert sum(1 for r in results if r is not None) == 1


def test_separate_nonces_two_provider_calls():
    provider = _FakeProvider()
    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="u1",
        conversation_id="c1",
        turn_id="t1",
    )
    from app.services.write_invoke_idempotency import build_write_idempotency_key

    k1, _ = build_write_idempotency_key(
        ctx, "gmail.messages.send", {"_write_idempotency_nonce": "a", "email": "a@x.com"}
    )
    k2, _ = build_write_idempotency_key(
        ctx, "gmail.messages.send", {"_write_idempotency_nonce": "b", "email": "a@x.com"}
    )
    assert k1 != k2
    _run_with_claim([WriteClaimResult(outcome="claimed")], provider)
    _run_with_claim([WriteClaimResult(outcome="claimed")], provider)
    assert provider.calls == 2
