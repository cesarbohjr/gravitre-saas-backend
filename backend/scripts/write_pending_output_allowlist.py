"""Write connector_output_pending_allowlist.py from catalog minus verified actions."""
from __future__ import annotations

from pathlib import Path

from app.services.connector_output_contract import VERIFIED_OUTPUT_ACTIONS, collect_write_action_keys

pending = sorted(collect_write_action_keys() - VERIFIED_OUTPUT_ACTIONS)
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
print(f"wrote {target} pending={len(pending)}")
