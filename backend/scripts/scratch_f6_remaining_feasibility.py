"""What is actually provable for the remaining F6 buckets, and against which vendors.

Phase 3 asks for each remaining action to be live-proven against its real
vendor. That is only possible where an active connector exists. This reports,
per bucket, which vendors are reachable right now and which are not, so the
remaining work is scoped by evidence instead of assumption.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
    if not p.is_file():
        continue
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            for k, v in (dotenv_values(p, encoding=enc) or {}).items():
                if v:
                    os.environ.setdefault(k, v)
            break
        except UnicodeDecodeError:
            continue

from app.config import get_settings  # noqa: E402
from app.connectors.action_catalog.registry import all_catalog_action_specs  # noqa: E402
from app.connectors.action_catalog.tool_aliases import resolve_registry_action  # noqa: E402
from app.services.tool_service import list_registered_actions  # noqa: E402
from app.services.write_success_verification import resolve_success_verification  # noqa: E402
from supabase import create_client  # noqa: E402

ORG = os.environ.get("F6_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")

STATE_VERBS = (
    "update", "set", "move", "change", "assign", "transition", "close", "archive",
    "enable", "disable", "activate", "deactivate", "approve", "reject", "publish",
    "cancel", "complete", "resolve", "rename", "mark",
)


def vendor_of(action: str) -> str:
    return action.split(".", 1)[0] if "." in action else action


def main() -> int:
    s = get_settings()
    sb = create_client(s.supabase_url, s.supabase_service_role_key)

    rows = (
        sb.table("connectors")
        .select("type,status")
        .eq("org_id", ORG)
        .is_("deleted_at", "null")
        .limit(500)
        .execute()
    ).data or []
    live_vendors = {
        str(r["type"]).lower()
        for r in rows
        if str(r.get("status") or "").lower() in {"active", "connected", "healthy"}
    }

    registered = set(list_registered_actions())
    buckets: dict[str, list[str]] = defaultdict(list)

    # Same mutating-action definition the coverage report uses, so the
    # denominator here is the 360 writes and not the whole 727 catalog.
    from app.services.write_success_verification import _mutating_specs

    for spec in _mutating_specs():
        action = str(spec.id)
        v = resolve_success_verification(action)
        if v.mode in {"follow_up_entity_get", "follow_up_field_assert", "follow_up_membership"}:
            buckets["already_covered"].append(action)
            continue
        if v.mode != "accepted_async":
            continue

        suffix = action.rsplit(".", 1)[-1].lower()
        vendor = vendor_of(action)
        is_state_change = any(suffix.startswith(w) or f"_{w}" in suffix for w in STATE_VERBS)

        get_sibling = f"{action.rsplit('.', 1)[0]}.get"
        list_sibling = f"{action.rsplit('.', 1)[0]}.list"
        has_get = resolve_registry_action(get_sibling, registered) in registered
        has_list = resolve_registry_action(list_sibling, registered) in registered

        if is_state_change and has_get:
            buckets["state_change_with_get"].append(action)
        elif has_get:
            buckets["other_with_get"].append(action)
        elif has_list:
            buckets["list_only"].append(action)
        else:
            buckets["no_registered_read"].append(action)

    out: dict = {
        "org_id": ORG,
        "mutating_action_total": sum(len(v) for v in buckets.values()),
        "live_connector_vendors": sorted(live_vendors),
        "live_connector_count": len(live_vendors),
        "buckets": {},
    }
    for name, actions in buckets.items():
        by_vendor: dict[str, int] = defaultdict(int)
        for a in actions:
            by_vendor[vendor_of(a)] += 1
        provable = sorted(v for v in by_vendor if v in live_vendors)
        blocked = sorted(v for v in by_vendor if v not in live_vendors)
        out["buckets"][name] = {
            "action_count": len(actions),
            "vendor_count": len(by_vendor),
            "vendors_with_live_connector": provable,
            "actions_live_provable_now": sum(by_vendor[v] for v in provable),
            "actions_blocked_no_connector": sum(by_vendor[v] for v in blocked),
            "blocked_vendor_sample": blocked[:25],
            "sample_actions": sorted(actions)[:12],
        }

    dest = REPO / "docs" / "delivery" / "f6-remaining-feasibility.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
