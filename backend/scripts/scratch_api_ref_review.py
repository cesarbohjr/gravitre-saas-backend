"""Full review dump: every undetermined action and every multi-candidate choice."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(__file__).resolve().parents[2] / "docs" / "delivery" / "api-reference-map.json"
doc = json.loads(DATA.read_text(encoding="utf-8"))

if len(sys.argv) > 1:
    for prefix in sys.argv[1:]:
        print("#" * 78)
        print(f"ENTRIES for {prefix!r}")
        print("#" * 78)
        for action, entry in doc["entries"].items():
            if action.startswith(prefix):
                flag = "" if entry.get("candidate_count", 1) == 1 else f"  [+{entry['candidate_count'] - 1} alt]"
                print(
                    f"{action:44s} {entry['api_reference']:52s} "
                    f"{entry.get('base_url') or '-'}\n{'':44s} {entry['source']}{flag}"
                )
    raise SystemExit(0)

print("#" * 78)
print(f"UNDETERMINED ({len(doc['undetermined'])}) — every one, with extractor notes")
print("#" * 78)
for row in sorted(doc["undetermined"], key=lambda r: r["action"]):
    print(f"\n{row['action']}")
    print(f"  module : {row.get('module') or '(none)'}")
    print(f"  key    : {row.get('registry_key') or '(none)'}")
    print(f"  reason : {row.get('reason')}")
    for note in row.get("notes") or []:
        print(f"  note   : {note}")

print()
print("#" * 78)
print(f"AMBIGUOUS ({len(doc['ambiguous'])}) — chosen vs all candidates")
print("#" * 78)
for row in sorted(doc["ambiguous"], key=lambda r: r["action"]):
    print(f"\n{row['action']}   [chosen: {row['chosen']}]")
    for cand in row["candidates"]:
        mark = "->" if cand["reference"] == row["chosen"] else "  "
        print(f"  {mark} {cand['reference']:56s} {cand['source']}")
