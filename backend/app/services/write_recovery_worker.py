"""Service-role recovery poller for durable uncertain write claims.

Invoke from an existing trusted scheduled job with a service-role database
client and a context factory that resolves the original tenant/connector
credentials. Never use a request/user client to enumerate recovery work.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.services.write_recovery_service import recover_uncertain_write

logger = logging.getLogger(__name__)


def process_due_write_recoveries(
    *,
    service_client: Any,
    context_factory: Callable[[str, str], Any],
    limit: int = 50,
) -> dict[str, int]:
    """Poll persisted recovery work; no mutating provider calls are issued.

    The context factory MUST resolve the original tenant-owned connector using
    trusted service-side credentials, never values from a user request.
    A single malformed entry does not prevent processing subsequent entries.
    """
    stats = {"seen": 0, "completed": 0, "not_applied": 0,
             "unknown": 0, "rejected": 0, "error": 0}
    try:
        result = service_client.rpc("list_due_write_recoveries", {
            "p_limit": max(1, min(int(limit), 100)),
        }).execute()
        rows = result.data
        if not isinstance(rows, list):
            raise ValueError("invalid recovery queue response")
    except Exception:
        logger.exception("write_recovery_queue_unavailable")
        stats["error"] += 1
        return stats

    for row in rows:
        stats["seen"] += 1
        try:
            org = str(row["org_id"])
            connector = str(row["connector_id"])
            action = str(row["invoke_action"])
            key = str(row["idempotency_key"])
            args = row["original_args"]
            if not all((org, connector, action, key)) or not isinstance(args, dict):
                stats["unknown"] += 1
                continue
            ctx = context_factory(org, connector)
            if (str(getattr(ctx, "org_id", "")) != org or
                    str(getattr(ctx, "connector_id", "")) != connector or
                    getattr(ctx, "client", None) is None):
                stats["rejected"] += 1
                continue
            # The recovery ledger must use the trusted service-role client,
            # not the connector's user-scoped credential.
            ctx.client = service_client
            outcome = recover_uncertain_write(
                ctx=ctx, idempotency_key=key,
                invoke_action=action, original_args=args,
            )
            stats[outcome.state] += 1
        except Exception:
            logger.exception("write_recovery_item_failed")
            stats["error"] += 1
    return stats
