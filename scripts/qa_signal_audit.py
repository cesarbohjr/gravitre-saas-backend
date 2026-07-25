"""Write platform golden-signal rows to audit_events (ops dashboard source)."""
from __future__ import annotations

import json
import os
from typing import Any

PLATFORM_ORG_ID = os.environ.get(
    "GRAVITRE_PLATFORM_SIGNALS_ORG_ID",
    "00000000-0000-4000-8000-000000000001",
)


def write_platform_signal(
    sb: Any,
    *,
    action: str,
    verdict: str,
    metadata: dict[str, Any] | None = None,
    resource_id: str | None = None,
) -> None:
    """Best-effort platform signal — never fails the caller."""
    try:
        meta = {"verdict": verdict, **(metadata or {})}
        sb.table("audit_events").insert(
            {
                "org_id": PLATFORM_ORG_ID,
                "actor_id": PLATFORM_ORG_ID,
                "action": action,
                "resource_type": "platform_signal",
                "resource_id": resource_id or action,
                "metadata": json.dumps(meta),
            }
        ).execute()
    except Exception:
        return
