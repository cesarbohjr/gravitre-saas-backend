"""One-off generator for PENDING_OUTPUT_SCHEMA_ALLOWLIST — run to refresh after verified set grows."""
from __future__ import annotations

from app.connectors.action_catalog.registry import all_catalog_action_specs

VERIFIED_OUTPUT_ACTIONS = frozenset({"apollo.lists.create", "slack.post_message"})

keys = sorted(
    {
        spec.id if "." in spec.id else spec.tool
        for spec in all_catalog_action_specs()
        if spec.kind == "write"
    }
)
pending = [key for key in keys if key not in VERIFIED_OUTPUT_ACTIONS]
print(f"# verified={len(VERIFIED_OUTPUT_ACTIONS)} pending={len(pending)}")
for key in pending:
    print(f'        "{key}",')
