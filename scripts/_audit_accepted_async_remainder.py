"""Why is each accepted_async action still unverified?

Phase 3.3 asks for the specific reason per action. "No sibling read is declared
in the catalog" and "the vendor genuinely cannot confirm this" are very
different answers, and only the first is established today. Splits the
remainder by whether a plausible sibling read already exists in the registry.
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

from app.connectors.action_catalog.tool_aliases import resolve_registry_action  # noqa: E402
from app.services.tool_service import list_registered_actions  # noqa: E402

CATALOG = pathlib.Path(
    "app/connectors/action_catalog/data/success_verification_catalog.json"
)


def executable(action: str, registered: set[str]) -> bool:
    return bool(action) and resolve_registry_action(action, registered) in registered


def candidate_reads(write_action: str) -> list[str]:
    """Sibling GETs a write of this shape would plausibly use."""
    parts = write_action.split(".")
    if len(parts) < 2:
        return []
    vendor = parts[0]
    resource = ".".join(parts[1:-1]) if len(parts) >= 3 else ""
    out = []
    if resource:
        out += [f"{vendor}.{resource}.get", f"{vendor}.{resource}.list"]
    out += [f"{vendor}.get_file_metadata"]
    return out


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["actions"]
    registered = set(list_registered_actions())

    remainder = [a for a, v in catalog.items() if v.get("mode") == "accepted_async"]

    reachable: list[tuple[str, str]] = []
    no_read: list[str] = []
    for action in sorted(remainder):
        hit = next((c for c in candidate_reads(action) if executable(c, registered)), None)
        if hit:
            reachable.append((action, hit))
        else:
            no_read.append(action)

    total = len(remainder)
    print(f"accepted_async remainder: {total}")
    print(f"  a plausible sibling read ALREADY EXISTS : {len(reachable)}")
    print(f"  no sibling read found in the registry   : {len(no_read)}")
    print()
    print("These are candidates for real read-back — not vendor limitations:")
    for action, read in reachable[:40]:
        print(f"   {action:44s} -> {read}")
    if len(reachable) > 40:
        print(f"   ... and {len(reachable) - 40} more")

    print()
    print("Top vendors in the no-sibling-read group:")
    for vendor, count in Counter(a.split(".")[0] for a in no_read).most_common(15):
        print(f"   {vendor:24s} {count}")

    print()
    print(
        "NOTE: 'no sibling read found' means Gravitre does not register one. It is "
        "NOT evidence the vendor API cannot confirm the write. That per-vendor "
        "determination has not been done."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
