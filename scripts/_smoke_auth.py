"""Shared smoke auth helpers — resolve prod actor without brittle admin lookups."""
from __future__ import annotations

from typing import Any


def resolve_smoke_actor_and_email(
    client: Any,
    *,
    org_id: str,
    env: dict[str, str],
) -> tuple[str, str]:
    """Pick a live org member for prod smokes; tolerate stale OAUTH_SMOKE_USER_ID secrets."""
    preferred = (env.get("OAUTH_SMOKE_USER_ID") or env.get("SMOKE_USER_ID") or "").strip()
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    rows = client.table("organization_members").select("user_id").eq("org_id", org_id).limit(5).execute()
    for row in rows.data or []:
        uid = str(row.get("user_id") or "").strip()
        if uid and uid not in candidates:
            candidates.append(uid)
    if not candidates:
        raise SystemExit(f"No organization_members rows for org_id={org_id}")

    for actor in candidates:
        try:
            users = client.auth.admin.get_user_by_id(actor)
            email = users.user.email if users and users.user else None
            if email:
                return actor, email
        except Exception:
            pass
        return actor, f"{actor}@gravitre.local"

    raise SystemExit("Unable to resolve smoke actor")
