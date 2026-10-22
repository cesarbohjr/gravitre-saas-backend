#!/usr/bin/env python3
"""Phase 3 coverage inventory gate. Inventory is NOT integration certification."""
import argparse
import json
from pathlib import Path

CAPABILITIES = ("contextual", "sentiment", "causal", "temporal", "relational", "adaptive", "predictive")
SURFACES = ("flows", "plays", "agents", "workflows", "connectors", "knowledge", "memory", "governance")
SCENARIOS = ("customer_support", "sales_operations", "it_incident_management")

def build():
    return {
        "schema": "gravitre.phase3.intelligence_coverage.v1",
        "certification": "NOT_CERTIFIED",
        "scenario_ids": list(SCENARIOS),
        "cells": [
            {"id": f"{capability}:{surface}", "capability": capability, "surface": surface,
             "status": "NOT_TESTED", "test_selector": None, "evidence_artifact": None}
            for capability in CAPABILITIES for surface in SURFACES
        ],
    }

def validate(payload):
    cells = payload.get("cells", [])
    expected = {f"{c}:{s}" for c in CAPABILITIES for s in SURFACES}
    ids = [c.get("id") for c in cells]
    if len(ids) != 56 or len(set(ids)) != 56 or set(ids) != expected:
        raise ValueError("Expected exactly 56 unique capability/surface cells")
    if payload.get("scenario_ids") != list(SCENARIOS):
        raise ValueError("Three mandatory scenario IDs are missing or reordered")
    for cell in cells:
        if cell["status"] not in ("NOT_TESTED", "PASS_OFFLINE_CONTRACT", "FAIL", "PASS_LIVE_VERIFIED"):
            raise ValueError("Unknown coverage status: " + str(cell["status"]))
        if cell["status"].startswith("PASS") and not (cell.get("test_selector") and cell.get("evidence_artifact")):
            raise ValueError("PASS requires test selector and evidence artifact: " + cell["id"])
    if payload.get("certification") == "CERTIFIED" and any(c["status"] != "PASS_LIVE_VERIFIED" for c in cells):
        raise ValueError("Cannot certify incomplete or offline-only coverage")
    return {"total": len(cells), "not_tested": sum(c["status"] == "NOT_TESTED" for c in cells),
            "offline_pass": sum(c["status"] == "PASS_OFFLINE_CONTRACT" for c in cells),
            "live_verified": sum(c["status"] == "PASS_LIVE_VERIFIED" for c in cells)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="phase3-evidence/intelligence-coverage.json")
    parser.add_argument("--require-certified", action="store_true")
    args = parser.parse_args()
    report = build()
    stats = validate(report)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({**report, "summary": stats}, indent=2) + "\n")
    print(json.dumps({"certification": report["certification"], **stats}))
    return 1 if args.require_certified and stats["live_verified"] != 56 else 0

if __name__ == "__main__":
    raise SystemExit(main())
