"""In-process pub/sub for live notification bell push (SSE subscribers per org/user)."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

_subscribers: dict[tuple[str, str], list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)


def subscribe(org_id: str, user_id: str, *, maxsize: int = 64) -> asyncio.Queue[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
    key = (str(org_id), str(user_id))
    _subscribers[key].append(queue)
    logger.debug("notification live bus subscribe org_id=%s user_id=%s", org_id, user_id)
    return queue


def unsubscribe(org_id: str, user_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
    key = (str(org_id), str(user_id))
    buckets = _subscribers.get(key)
    if not buckets:
        return
    try:
        buckets.remove(queue)
    except ValueError:
        return
    if not buckets:
        _subscribers.pop(key, None)
    logger.debug("notification live bus unsubscribe org_id=%s user_id=%s", org_id, user_id)


def publish(org_id: str, user_id: str, payload: dict[str, Any]) -> int:
    key = (str(org_id), str(user_id))
    delivered = 0
    for queue in list(_subscribers.get(key, [])):
        try:
            queue.put_nowait(payload)
            delivered += 1
        except asyncio.QueueFull:
            logger.debug(
                "notification live bus queue full org_id=%s user_id=%s — dropping oldest",
                org_id,
                user_id,
            )
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


def reset_subscribers_for_tests() -> None:
    _subscribers.clear()
