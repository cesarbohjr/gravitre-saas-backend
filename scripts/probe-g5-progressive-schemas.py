#!/usr/bin/env python3
"""Before/after progressive disclosure payload probe (same TTFT probe set).

Measures tools_payload_bytes for narrowed full schemas vs progressive stubs
on the email/list/enrich probe strings from unified-turn-task-ttft-baseline.
Does not call the model — comparable compression evidence for G.5.2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.agent_platform_optimizer import narrow_tools_for_turn
from app.services.progressive_tool_schemas import (
    apply_progressive_disclosure,
    payload_bytes,
)
from app.services.tool_registry import get_tool_registry
from app.services.unified_turn_tool_retrieval import is_task_shaped_for_retrieval

PROBES = [
    ("email_intent", "Send an email to Stephanie about the proposal"),
    ("list_create", "Create a HubSpot static list named MSPs"),
    ("msp_enrich", 'Use Clay to enrich Apollo list "MSP Prospects" into HubSpot MSPs'),
    ("advise_only", "Don't take any action — just advise me on HubSpot vs Apollo lists"),
    ("github_issues", "search GitHub issues mentioning billing"),
]

CONNECTED = ["apollo", "hubspot", "clay", "gmail", "slack", "github", "platform"]
OUT = REPO / "docs" / "delivery" / "g5-progressive-schemas-probe.json"


def main() -> int:
    registry = get_tool_registry()
    all_tools = registry.get_tools_for_agent(["*"], CONNECTED)
    rows = []
    for pid, message in PROBES:
        use_embed, shape, query = is_task_shaped_for_retrieval(message)
        max_tools = 16 if use_embed else 32
        narrowed, stats = narrow_tools_for_turn(
            all_tools,
            query=query or message,
            connected_integrations=CONNECTED,
            max_tools=max_tools,
        )
        full_bytes = payload_bytes(list(narrowed))
        attach, _, _ = apply_progressive_disclosure(list(narrowed))
        prog_bytes = payload_bytes(list(attach))
        rows.append(
            {
                "id": pid,
                "message": message,
                "turn_shape": shape,
                "total_catalog": len(all_tools),
                "visible_tools": len(narrowed),
                "max_tools_cap": max_tools,
                "before_full_narrowed_bytes": full_bytes,
                "after_progressive_bytes": prog_bytes,
                "bytes_reduction_pct": round(
                    100.0 * (1.0 - prog_bytes / max(1, full_bytes)), 2
                ),
                "retrieval_method": stats.get("retrievalMethod")
                or "keyword_narrow_tools_for_turn",
            }
        )
    avg_before = sum(r["before_full_narrowed_bytes"] for r in rows) / len(rows)
    avg_after = sum(r["after_progressive_bytes"] for r in rows) / len(rows)
    report = {
        "probe": "g5_progressive_schemas",
        "note": (
            "Token/latency model_ttft requires live OpenAI; this probe reports "
            "comparable tools payload bytes on the TTFT probe set. Accuracy is "
            "covered by withhold_no_tool CI battery."
        ),
        "avg_before_full_narrowed_bytes": int(avg_before),
        "avg_after_progressive_bytes": int(avg_after),
        "avg_bytes_reduction_pct": round(100.0 * (1.0 - avg_after / max(1, avg_before)), 2),
        "probes": rows,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
