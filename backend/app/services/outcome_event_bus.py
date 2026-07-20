"""Org-scoped live stream for Module A execution outcomes.

Reuses the same in-process pub/sub pattern as notification_live_bus so future
subscribers (ops dashboard, Weekly Business Digest) can react to terminal
outcomes without re-deriving state from workflow_runs.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

_subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)


def subscribe_outcomes(org_id: str, *, maxsize: int = 128) -> asyncio.Queue[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
    key = str(org_id)
    _subscribers[key].append(queue)
    logger.debug("outcome_event_bus subscribe org_id=%s", org_id)
    return queue


def unsubscribe_outcomes(org_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
    key = str(org_id)
    buckets = _subscribers.get(key)
    if not buckets:
        return
    try:
        buckets.remove(queue)
    except ValueError:
        return
    if not buckets:
        _subscribers.pop(key, None)


def publish_outcome(org_id: str, payload: dict[str, Any]) -> int:
    key = str(org_id)
    delivered = 0
    for queue in list(_subscribers.get(key, [])):
        try:
            queue.put_nowait(payload)
            delivered += 1
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(payload)
                delivered += 1
            except asyncio.QueueFull:
                pass
    return delivered


def reset_outcome_subscribers_for_tests() -> None:
    _subscribers.clear()
