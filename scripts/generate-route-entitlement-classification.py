"""Generate complete route entitlement classification table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.billing.route_entitlement_registry import classify_all_routes  # noqa: E402


def main() -> None:
    inventory_path = REPO / "docs" / "delivery" / "route-inventory.json"
    routes = json.loads(inventory_path.read_text(encoding="utf-8"))
    decisions = classify_all_routes(routes)
    rows = [
        {
            "method": d.method,
            "path": d.path,
            "tier_required": d.tier_required,
            "guard_present": d.guard_present,
            "guard_location": d.guard_location,
            "status": d.status,
            "notes": d.notes,
        }
        for d in decisions
    ]
    out = REPO / "docs" / "delivery" / "route-entitlement-classification.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    guarded = sum(1 for r in rows if r["status"] == "correctly_guarded")
    unguarded = sum(1 for r in rows if r["status"] == "correctly_unguarded")
    gap = sum(1 for r in rows if r["status"] == "gap_needs_guard")
    print(f"Wrote {len(rows)} rows to {out}")
    print(f"correctly_guarded={guarded} correctly_unguarded={unguarded} gap={gap}")


if __name__ == "__main__":
    main()
