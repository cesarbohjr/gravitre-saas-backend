#!/usr/bin/env python3
"""One-time Module B sweep: schema-primary heuristic on every write-capable action.

Confirms write actions with coverable schema fields do not silently return empty
extraction the way Zendesk originally did. Writes
docs/delivery/module-b-schema-extraction-sweep.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.connectors.action_catalog.action_workflow_schema import (  # noqa: E402
    get_workflow_schema,
    iter_workflow_fields,
)
from app.connectors.action_catalog.registry import all_catalog_action_specs  # noqa: E402
from app.services.schema_param_extractor import extract_action_args_heuristic  # noqa: E402

OUT = ROOT / "docs" / "delivery" / "module-b-schema-extraction-sweep.json"

# Keys the FAST heuristic is designed to fill from NL (Module B contract).
COVERABLE_KEYS = {
    "to",
    "email",
    "channel",
    "channel_id",
    "title",
    "name",
    "summary",
    "subject",
    "body",
    "text",
    "message",
    "project_key",
    "project",
    "list_id",
    "list_name",
}


def _sample_message(action_id: str, field_keys: list[str]) -> str:
    """Build a NL message that should fill at least one coverable schema field."""
    vendor = action_id.split(".", 1)[0].replace("_", " ")
    noun = action_id.split(".")[-1].replace("_", " ")
    if any(k in field_keys for k in ("title", "name", "summary", "subject")):
        return f'create a {vendor} {noun} titled "Module B sweep {noun}"'
    if any(k in field_keys for k in ("to", "email")):
        return f"create a {vendor} {noun} for sweep.moduleb@acme.test"
    if "channel" in field_keys or "channel_id" in field_keys:
        return f"post a {vendor} {noun} to #module-b-sweep saying hello from sweep"
    if "project_key" in field_keys or "project" in field_keys:
        return f"create a {vendor} {noun} login page broken in project ENG"
    if "list_id" in field_keys or "list_name" in field_keys:
        return f'create a {vendor} list called "module-b-sweep-list"'
    if any(k in field_keys for k in ("body", "text", "message")):
        return f'send a {vendor} {noun} saying "Module B sweep body"'
    return f'run {vendor} {noun} called "Module B sweep {noun}"'


def _field_keys(action_id: str) -> list[str]:
    schema = get_workflow_schema(action_id)
    if not schema:
        return []
    keys: list[str] = []
    for field in iter_workflow_fields(schema):
        arg_keys = getattr(field, "arg_keys", None) or ()
        if arg_keys:
            keys.append(arg_keys[0])
    return keys


def main() -> int:
    rows: list[dict[str, Any]] = []
    write_specs = [
        s
        for s in all_catalog_action_specs()
        if str(getattr(s, "kind", "") or "").lower() in {"write", "advanced"}
    ]
    for spec in write_specs:
        action_id = spec.id
        keys = _field_keys(action_id)
        if not keys:
            rows.append(
                {
                    "action": action_id,
                    "kind": spec.kind,
                    "has_schema": False,
                    "verdict": "SKIP_NO_SCHEMA",
                    "note": "No workflow schema — schema-primary extract cannot run",
                }
            )
            continue
        coverable = [k for k in keys if k in COVERABLE_KEYS]
        if not coverable:
            rows.append(
                {
                    "action": action_id,
                    "kind": spec.kind,
                    "has_schema": True,
                    "schema_keys": keys,
                    "verdict": "SKIP_OPAQUE_KEYS",
                    "note": "Schema keys are ids/payloads outside FAST heuristic contract",
                }
            )
            continue
        message = _sample_message(action_id, keys)
        args = extract_action_args_heuristic(action_id, message)
        meaningful = {
            k: v
            for k, v in (args or {}).items()
            if isinstance(v, str) and len(v.strip()) >= 2
        }
        hit = any(str(meaningful.get(k) or "").strip() for k in coverable)
        verdict = "PASS" if hit else "FAIL_EMPTY"
        rows.append(
            {
                "action": action_id,
                "kind": spec.kind,
                "has_schema": True,
                "schema_keys": keys,
                "coverable_keys": coverable,
                "message": message,
                "extracted": args,
                "meaningful": meaningful,
                "verdict": verdict,
            }
        )

    by: dict[str, int] = {}
    for r in rows:
        by[r["verdict"]] = by.get(r["verdict"], 0) + 1

    fail_empty = [r["action"] for r in rows if r["verdict"] == "FAIL_EMPTY"]
    report = {
        "module": "B",
        "audit": "schema_extraction_write_catalog_sweep",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "write_action_count": len(write_specs),
        "coverable_contract_keys": sorted(COVERABLE_KEYS),
        "counts": by,
        "fail_empty": fail_empty,
        "skip_no_schema_count": by.get("SKIP_NO_SCHEMA", 0),
        "skip_opaque_keys_count": by.get("SKIP_OPAQUE_KEYS", 0),
        "rows": rows,
        # Generalization proof: every coverable write action extracts something.
        "sweep_pass": by.get("FAIL_EMPTY", 0) == 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "write_action_count": report["write_action_count"],
                "counts": by,
                "sweep_pass": report["sweep_pass"],
                "fail_empty": fail_empty,
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if report["sweep_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
