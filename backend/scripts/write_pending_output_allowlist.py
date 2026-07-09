"""Write connector_output_pending_allowlist.py from current catalog debt."""
from __future__ import annotations

from pathlib import Path

from app.connectors.action_catalog.registry import all_catalog_action_specs
from app.services.connector_output_contract import VERIFIED_OUTPUT_ACTIONS

keys = sorted(
    {
        spec.id if "." in spec.id else spec.tool
        for spec in all_catalog_action_specs()
        if spec.kind == "write"
    }
)
pending = [key for key in keys if key not in VERIFIED_OUTPUT_ACTIONS]
target = Path(__file__).resolve().parents[1] / "app" / "services" / "connector_output_pending_allowlist.py"
lines = [
    '"""Generated pending output schema debt — shrink as actions gain verified summaries/result_url."""',
    "from __future__ import annotations",
    "",
    "PENDING_OUTPUT_SCHEMA_ALLOWLIST: frozenset[str] = frozenset(",
    "    {",
]
lines.extend(f'        "{key}",' for key in pending)
lines.extend(["    }", ")", ""])
target.write_text("\n".join(lines), encoding="utf-8")
print(f"verified={len(VERIFIED_OUTPUT_ACTIONS)} pending={len(pending)} -> {target}")
