"""Extract FastAPI route inventory for entitlement audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.main import app  # noqa: E402


def main() -> None:
    rows: list[dict[str, str]] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        name = getattr(route, "name", "")
        if not path or path.startswith("/openapi") or path.startswith("/docs"):
            continue
        for method in sorted(methods):
            if method in {"HEAD", "OPTIONS"}:
                continue
            rows.append({"method": method, "path": path, "name": name})
    rows.sort(key=lambda r: (r["path"], r["method"]))
    out = REPO / "docs" / "delivery" / "route-inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} routes to {out}")

if __name__ == "__main__":
    main()
