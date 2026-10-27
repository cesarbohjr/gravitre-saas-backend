#!/usr/bin/env python3
"""Phase 3 coverage inventory gate. Inventory is NOT integration certification."""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
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

def apply_junit_contracts(report, junit):
    """Accept executed, complete role/channel sets; never promote to live status."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.operators.agent_prompts import AGENT_PERSONAS

    expected = {(role, channel) for role in AGENT_PERSONAS for channel in ("text", "voice")}
    groups = {cell["id"]: {} for cell in report["cells"]}
    for case in ET.parse(junit).iter("testcase"):
        props = {p.get("name"): p.get("value") for p in case.findall("./properties/property")}
        if props.get("evidence_scope") != "shared_adapter_contract":
            continue
        key = props.get("phase3_cell")
        identity = (props.get("phase3_role"), props.get("phase3_channel"))
        if key not in groups or identity not in expected or identity in groups[key]:
            raise ValueError("Invalid or duplicated shared-adapter evidence")
        groups[key][identity] = not any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
    for cell in report["cells"]:
        cases = groups[cell["id"]]
        cell["role_channel_cases"] = len(cases)
        cell["required_role_channel_cases"] = len(expected)
        cell["evidence_scope"] = "shared_adapter_contract"
        if cases and not all(cases.values()):
            cell["status"] = "FAIL"
        elif set(cases) == expected:
            cell.update(status="PASS_OFFLINE_CONTRACT",
                        test_selector="tests/services/test_phase3_one_brain_contract.py::test_shared_adapter_capabilities_reach_consumers",
                        evidence_artifact=str(junit))
    report["coverage_scope"] = "shared_adapter_contract"
    report["full_product_journeys_verified"] = False
    report["roles"] = list(AGENT_PERSONAS)
    report["channels"] = ["text", "voice"]
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="phase3-evidence/intelligence-coverage.json")
    parser.add_argument("--require-certified", action="store_true")
    parser.add_argument("--junit", type=Path, help="Executed shared-adapter contract evidence")
    parser.add_argument("--require-offline", action="store_true")
    args = parser.parse_args()
    report = build()
    if args.junit:
        report = apply_junit_contracts(report, args.junit)
    stats = validate(report)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({**report, "summary": stats}, indent=2) + "\n")
    print(json.dumps({"certification": report["certification"], **stats}))
    return 1 if ((args.require_certified and stats["live_verified"] != 56)
                 or (args.require_offline and stats["offline_pass"] != 56)) else 0

if __name__ == "__main__":
    raise SystemExit(main())
