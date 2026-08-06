"""Write platform golden-signal rows to audit_events (ops dashboard source)."""
from __future__ import annotations

import json
import os
from typing import Any

# Must be a real organizations.id (FK). Default: isolated conversation smoke org.
PLATFORM_ORG_ID = os.environ.get(
    "GRAVITRE_PLATFORM_SIGNALS_ORG_ID",
    "f07e57c0-1501-4000-8000-c04e57a00001",
)
PLATFORM_ACTOR_ID = os.environ.get(
    "GRAVITRE_PLATFORM_SIGNALS_ACTOR_ID",
    "a9f1240f-910a-42ca-aebf-38caeac288c3",
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
                "actor_id": PLATFORM_ACTOR_ID,
                "action": action,
                "resource_type": "platform_signal",
                "resource_id": resource_id or "00000000-0000-4000-8000-0000000000aa",
                "metadata": json.dumps(meta),
            }
        ).execute()
    except Exception:
        return
