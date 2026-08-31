"""Print the real executor source for every undetermined action, for hand review."""
from __future__ import annotations

import inspect
import json
import sys
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

from app.connectors.action_catalog.tool_aliases import registry_keys_for_catalog_tool
from app.services.tool_service import _TOOL_REGISTRY

doc = json.loads((REPO / "docs" / "delivery" / "api-reference-map.json").read_text(encoding="utf-8"))


def resolve(action: str):
    fn = _TOOL_REGISTRY.get(action)
    if fn is not None:
        return fn
    for key in sorted(registry_keys_for_catalog_tool(action)):
        fn = _TOOL_REGISTRY.get(key)
        if fn is not None:
            return fn
    return None


for row in sorted(doc["undetermined"], key=lambda r: r["action"]):
    action = row["action"]
    print("=" * 78)
    print(action)
    fn = resolve(action)
    if fn is None:
        print("  (no executor registered)")
        continue
    print(f"  {fn.__module__}.{fn.__qualname__}")
    try:
        src = textwrap.dedent(inspect.getsource(fn))
    except Exception as exc:
        print(f"  source unavailable: {exc}")
        continue
    print(textwrap.indent(src[:1100], "  "))
