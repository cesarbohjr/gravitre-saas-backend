"""Classify every catalog action by where its real HTTP endpoint comes from.

This is the prerequisite survey for api_reference: before mapping 727 actions to
endpoints we need to know, per action, which implementation actually issues the
request. Three provenance classes exist and they are NOT equally trustworthy:

  route_table   - a hand-written method+path table (phase2, twilio). Real.
  dedicated     - a purpose-written executor function. Real, needs source read.
  name_inferred - the generic catalog_http executor, which derives method+path
                  from the action *suffix* via _infer_route(). The route is what
                  the code really sends, but it was never checked against the
                  vendor's actual API.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.connectors.action_catalog.registry import get_vendor_catalog
from app.connectors.action_catalog.tool_aliases import registry_keys_for_catalog_tool
from app.connectors.phase2_connector_routes import PHASE2_ROUTES
from app.services.tool_service import _TOOL_REGISTRY


def catalog_action_ids() -> list[str]:
    ids: set[str] = set()
    for vendor_spec in get_vendor_catalog().values():
        for action in vendor_spec.all_actions():
            tool_key = action.id
            if "." not in tool_key or tool_key.split(".", 1)[0] != vendor_spec.vendor:
                tool_key = f"{vendor_spec.vendor}.{action.id}"
            ids.add(tool_key)
    return sorted(ids)


def resolve_executor(action: str):
    """Mirror invoke_tool's lookup: canonical id first, then registry aliases."""
    fn = _TOOL_REGISTRY.get(action)
    if fn is not None:
        return action, fn
    for key in sorted(registry_keys_for_catalog_tool(action)):
        fn = _TOOL_REGISTRY.get(key)
        if fn is not None:
            return key, fn
    return None, None


def classify(action: str, fn) -> tuple[str, str]:
    if fn is None:
        return "unregistered", ""
    module = getattr(fn, "__module__", "") or ""
    if module == "app.connectors.catalog_http.executor":
        return "name_inferred", module
    if module == "app.connectors.twilio_tools":
        return "route_table", module
    if action in PHASE2_ROUTES or module == "app.connectors.phase2_connector_tools":
        return "route_table", module
    return "dedicated", module


def main() -> int:
    actions = catalog_action_ids()
    rows = []
    klass_counts: Counter[str] = Counter()
    module_counts: Counter[str] = Counter()

    for action in actions:
        key, fn = resolve_executor(action)
        klass, module = classify(action, fn)
        klass_counts[klass] += 1
        if klass == "dedicated":
            module_counts[module] += 1
        rows.append(
            {
                "action": action,
                "registry_key": key,
                "class": klass,
                "module": module,
                "qualname": getattr(fn, "__qualname__", "") if fn else "",
            }
        )

    out = {
        "catalog_action_total": len(actions),
        "by_class": dict(klass_counts),
        "dedicated_modules": dict(module_counts.most_common()),
        "rows": rows,
    }
    dest = Path(__file__).resolve().parents[2] / "docs" / "delivery" / "action-executor-provenance.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"catalog actions: {len(actions)}")
    for klass, count in klass_counts.most_common():
        print(f"  {klass:14s} {count:4d}")
    print(f"\ndedicated executor modules: {len(module_counts)}")
    for module, count in module_counts.most_common(40):
        print(f"  {count:4d}  {module}")
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
