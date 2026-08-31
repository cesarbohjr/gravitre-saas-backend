"""Print the live loop artifact in readable form."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ART = Path(__file__).resolve().parents[2] / "docs" / "delivery" / "evidence-sufficiency-loop-live.json"

data = json.loads(ART.read_text(encoding="utf-8"))
for turn in data["turns"]:
    print("===", turn["label"], "===")
    k = turn.get("unifiedTurnKnowledge") or {}
    for key in (
        "pack_ids",
        "route_reason",
        "fabric_hit_count",
        "org_rag_chunk_count",
        "internet_hit_count",
        "internet_raw_hit_count",
        "internet_empty_relevant",
        "internet_provider",
        "internal_thin",
        "business_graph_status",
        "skipped",
    ):
        print(f"  {key:24} {k.get(key)}")
    es = k.get("evidenceSufficiency") or {}
    print(f"  {'bar':24} {es.get('bar')}")
    print(f"  {'sources_tried':24} {es.get('sources_tried')}")
    print(f"  {'additional_rounds_used':24} {es.get('additional_rounds_used')} / {es.get('max_additional_rounds')}")
    print(f"  {'loop_ms':24} {es.get('ms')}")
    for i, a in enumerate(es.get("assessments") or []):
        print(f"  assessment[{i}] sufficient={a.get('sufficient')} assessor={a.get('assessor')}")
        print(f"      bar={a.get('bar')} gaps={a.get('gaps')}")
        print(f"      reason={a.get('reason')}")
    print(f"  {'assistant_excerpt':24} {(turn.get('assistant_excerpt') or '')[:260]!r}")
    print()
