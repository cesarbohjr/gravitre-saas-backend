"""Summarize api_reference extraction gaps (reads the JSON only — no app import)."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(__file__).resolve().parents[2] / "docs" / "delivery" / "api-reference-map.json"
doc = json.loads(DATA.read_text(encoding="utf-8"))

print("=" * 72)
print("UNDETERMINED by module / reason")
by_module: Counter[str] = Counter()
reasons: Counter[str] = Counter()
samples: dict[str, list[str]] = defaultdict(list)
for row in doc["undetermined"]:
    module = row.get("module") or "(unregistered)"
    by_module[module] += 1
    reasons[row.get("reason", "?")] += 1
    if len(samples[module]) < 6:
        samples[module].append(row["action"])
for module, count in by_module.most_common():
    print(f"{count:4d}  {module}")
    print(f"        e.g. {', '.join(samples[module])}")
print()
for reason, count in reasons.most_common():
    print(f"{count:4d}  {reason}")

print("=" * 72)
print("AMBIGUOUS (multiple call sites) by module")
amb: Counter[str] = Counter()
for row in doc["ambiguous"]:
    amb[row.get("module") or "?"] += 1
for module, count in amb.most_common():
    print(f"{count:4d}  {module}")
print()
for row in doc["ambiguous"][:12]:
    print(f"- {row['action']}")
    for cand in row["candidates"]:
        print(f"    {cand['reference']:52s} {cand['source']}")

print("=" * 72)
print("SAMPLE dedicated single-hit entries (spot readability check)")
shown = 0
for action, entry in doc["entries"].items():
    if entry.get("provenance") == "dedicated" and entry.get("candidate_count") == 1:
        print(f"{action:44s} {entry['api_reference']:46s} {entry['source']}")
        shown += 1
        if shown >= 25:
            break
