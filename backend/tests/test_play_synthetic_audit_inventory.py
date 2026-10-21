"""Catalog-wide audit inventory. This is NOT an end-to-end execution certification.

The JSON artifact deliberately uses BLOCKED until a Play has an independently
verified synthetic runtime scenario. Never infer PASS from catalog registration.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.plays.catalog import STATIC_PLAY_TEMPLATES, platform_play_templates
from app.outcome_packs.registry import play_assets


def test_every_registered_play_is_accounted_for_in_synthetic_audit_inventory() -> None:
    plays = platform_play_templates()
    keys = [p.key for p in plays]
    assert keys, "No Plays registered"
    assert len(keys) == len(set(keys)), "Duplicate Play keys in catalog"
    expected = {p.key for p in STATIC_PLAY_TEMPLATES}
    expected.update(asset.key for _, asset in play_assets())
    assert set(keys) == expected, f"Unaccounted Plays: {sorted(expected ^ set(keys))}"

    records = [
        {
            "play_key": play.key,
            "department": play.department,
            "status": "BLOCKED",
            "reason": "Synthetic end-to-end workflow execution not evidenced by this inventory test",
            "catalog_registered": True,
            "synthetic_execution_verified": False,
        }
        for play in sorted(plays, key=lambda p: p.key)
    ]
    output = Path(os.environ.get("PLAYS_AUDIT_REPORT_PATH", "/tmp/plays-synthetic-audit-inventory.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"schema_version": 1, "scope": "synthetic", "results": records}, indent=2) + "\n",
        encoding="utf-8",
    )
    assert len(records) == len(expected)
